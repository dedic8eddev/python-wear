"""List some Exceptions. Implement Authorization Policy."""

import sys
from enum import Enum, unique

from pyramid.authorization import ACLAllowed, ACLDenied, Allow, Authenticated, Everyone
from pyramid.location import lineage
from pyramid.security import Allowed, Denied
from pyramid.util import is_nonstr_iter

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction

from spynl.api.auth.exceptions import TenantDoesNotExist
from spynl.api.auth.resources import B2BResource, Tenants, User
from spynl.api.auth.tenantid_utils import (
    extend_filter_by_tenant_id,
    reject_search_by_tenant_id,
    validate_tenant_id,
)
from spynl.api.auth.utils import MASTER_TENANT_ID, lookup_tenant
from spynl.api.mongo import MongoResource

if sys.version_info > (3,):  # pragma: nocover
    basestring = str


# TenantPrincipals
# These are checked to see if a logged in user may act upon tenants.


@unique
class Principals(Enum):
    """Our custom principals."""

    BelongsToTenant = 'BelongsToTenant'
    NoNeedToBelongToTenant = 'NoNeedToBelongToTenant'
    TenantActive = 'TenantActive'
    RequestedTenantActive = 'RequestedTenantActive'
    HasAccessToRequestedTenant = 'HasAccessToRequestedTenant'
    B2BAccess = 'B2BAccess'
    AccessingMasterTenant = 'AccessingMasterTenant'


class MultiAuthPolicySelected(object):
    """Event for tracking which authentication policy was used.

    This event is fired whenever a particular backend policy is successfully
    used for authentication.  It can be used by other parts of the code in
    order to act based on the selected policy::

        from pyramid.events import subscriber

        @subscriber(MultiAuthPolicySelected)
        def track_policy(event):
            print("We selected policy %s" % event.policy)

    """

    def __init__(self, policy, request, userid=None):
        self.policy = policy
        self.policy_name = getattr(policy, "_pyramid_multiauth_name", None)
        self.request = request
        self.userid = userid


class IAuthorizationPolicy:

    """An object representing a Pyramid Security policy."""

    def __init__(self, policies, callback=None):
        self._policies = policies
        self._callback = callback

    def permits(self, request, context, permission):
        """
        Return ``True`` (Allow) if any of the ``roles`` is allowed the
        ``permission`` in the current ``context``, else raise an
        HTTPException (Deny).
        Roles are computed by rolefinder and added to the principals
        list - which also stores whether the user authenticated and
        the user ID.

        We perform the following checks in this order:
        1. Allow pre-flight (OPTIONS) requests.
           (The frontend needs to use this because spynl is in a different
            domain than the frontend, the browser will not do the rest of the
            request if the options call fails)
        2. Deny if the user is not authenticated.
        3. Allow if being authenticated suffices.
        4. Verify that user belongs to tenant if the NoNeedToBelongToTenant
           principal is not present.
        5. Verify that tenant is active.
        6. If the current_tenant is NOT the master tenant, we restrict access
           to tenants other than the current tenant (B2BAccess):
           6a. The user can only access a B2B resource.
           6b. The requested tenant needs to be active.
           6c. The user needs to have access to the requested tenant (this
               is determined in the authentication callback).
        7. Deny access to certain resources if the requested tenant is the
           master tenant.
        8. Allow if one of the roles of the current user
           has the permissions for the context. This uses ACLs of
           the context resource or its ancestors (lineage). Relevant terms:
           An ACL is the full Access control list for a resource.
           An ACE is an access control entry in that list, which might get
           used to either Deny or Allow the request.

        N.B. Because of our implementation, there is a difference between
        setting permission=Authenticated when registering an endpoint, and
        adding Authenticated to an ACL. In the first case, we do not do any
        tenant checks, not even the BelongsToTenant. In the second case, a
        tenant does have to be set, and the user needs to belong to the current
        tenant. (A user cannot login without having access to a tenant, see
        login, but in the first case that tenant does not have to be set, but
        login automatically sets a tenant, so that doesn't happen)
        """
        principals = self.effective_principals(request)
        localizer = request.localizer

        principals = append_authorization_principals(request, principals)
        print(principals)

        if request.method == 'OPTIONS':
            return Allowed(_('auth-pre-flight-requests-allowed').translate(localizer))

        if Authenticated not in principals:
            return Denied(_('auth-anonymous-access').translate(localizer))

        if permission == Authenticated:
            return Allowed(_('auth-authenticated-allowed').translate(localizer))

        if (
            Principals.NoNeedToBelongToTenant not in principals
            and Principals.BelongsToTenant not in principals
        ):
            return Denied(_('auth-tenant-not-allowed-for-user').translate(localizer))

        if Principals.TenantActive not in principals:
            return Denied(
                _(
                    'auth-no-active-tenant',
                    mapping={'tenant': request.current_tenant_id},
                ).translate(localizer)
            )

        if Principals.B2BAccess in principals:
            # you can only access B2BRecources
            if not isinstance(context, B2BResource):
                return Denied(_('auth-not-a-b2b-context').translate(localizer))

            if Principals.RequestedTenantActive not in principals:
                return Denied(
                    _(
                        'auth-requested-tenant-not-active',
                        mapping={'tenant': request.requested_tenant_id},
                    ).translate(localizer)
                )

            if Principals.HasAccessToRequestedTenant not in principals:
                return Denied(
                    _(
                        'auth-requested-tenant-no-access',
                        mapping={'tenant': request.requested_tenant_id},
                    ).translate(localizer)
                )

        if Principals.AccessingMasterTenant in principals:
            if permission != 'read':
                return Denied(
                    _('auth-do-not-change-master-tenant').translate(localizer)
                )

        return self.check_acls(context, principals, permission)

    def principals_allowed_by_permission(self, context, permission):
        """Return a set of principal identifiers allowed by the
        ``permission`` in ``context``.  This behavior is optional; if you
        choose to not implement it you should define this method as
        something which raises a ``NotImplementedError``.
        This method will only be called when the
        ``pyramid.security.principals_allowed_by_permission`` API is used.
        """
        raise NotImplementedError

    def effective_principals(self, request):
        """Get the list of effective principals for this request.

        This method returns the union of the principals returned by each
        authn policy.  If a groupfinder callback is registered, its output
        is also added to the list.
        """
        principals = set((Everyone,))
        for policy in self._policies:
            principals.update(policy.effective_principals(request))
        if self._callback is not None:
            principals.discard(Authenticated)
            groups = None
            for policy in self._policies:
                userid = policy.authenticated_userid(request)
                if userid is None:
                    continue
                request.registry.notify(
                    MultiAuthPolicySelected(policy, request, userid)
                )
                groups = self._callback(userid, request)
                if groups is not None:
                    break
            if groups is not None:
                principals.add(userid)
                principals.add(Authenticated)
                principals.update(groups)
        return list(principals)

    def check_acls(self, context, principals, permission):
        """
        Return an instance of ACLAllowed if the policy
        permits access; return an instance of ACLDenied if not.
        Access is granted or denied if an ACE fits to this request.
        The requests fits if the role of an ACE is one of the roles
        the user has for this request and if the needed permission
        for this request is in the ACE role list.
        This is based on pyramid.authorization.ACLAuthorizationPolicy
        but extended for our use case.
        """
        acl = '<No ACL found on any object in resource lineage>'
        for location in lineage(context):
            print(location)
            try:
                print(location.__acl__)
                acl = location.__acl__
            except AttributeError:
                continue

            if acl and callable(acl):
                acl = acl()

            for ace in acl:
                ace_action, ace_role, ace_permissions = ace[0], ace[1], ace[2]
                if ace_role not in principals:
                    continue

                if not is_nonstr_iter(ace_permissions):
                    ace_permissions = [ace_permissions]
                if permission not in ace_permissions:
                    continue

                if ace_action == Allow:
                    if not hasattr(context, 'allowed_ace'):
                        context.allowed_ace = ace

                    return ACLAllowed(ace, acl, permission, principals, location)
                else:
                    if not hasattr(context, 'denied_ace'):
                        context.denied_ace = ace
                    return ACLDenied(ace, acl, permission, principals, location)

        # default deny (if no ACL in lineage at all, or if none of the
        # roles were mentioned in any ACE we found)
        return ACLDenied('<default deny>', acl, permission, principals, context)

    def load_identity(self, request):
        user = None
        for policy in self._policies:
            userid = policy.unauthenticated_userid(request)
            if userid is not None:
                user = request.db.users.find_one({'_id': userid, 'active': True})
                if user is not None:
                    break
        return user

    def identity(self, request):
        return self.load_identity(request)

    def unauthenticated_userid(self, request):
        """Find the unauthenticated userid for this request.

        This method delegates to each authn policy in turn, taking the
        userid from the first one that doesn't return None.
        """
        userid = None
        user = self.load_identity(request)
        if user is not None:
            userid = user['_id']
        return userid

    def authenticated_userid(self, request):
        """Find the authenticated userid for this request.

        This method delegates to each authn policy in turn, taking the
        userid from the first one that doesn't return None.  If a
        groupfinder callback is configured, it is also used to validate
        the userid before returning.
        """
        userid = None
        for policy in self._policies:
            userid = policy.unauthenticated_userid(request)
            if userid is not None:
                request.registry.notify(
                    MultiAuthPolicySelected(policy, request, userid)
                )
                if self._callback is None:
                    break
                if self._callback(userid, request) is not None:
                    break
                else:
                    userid = None
        return userid

    def get_policies(self):
        """Get the list of contained authentication policies, as tuple of
        name and instances.

        This may be useful to instrospect the configured policies, and their
        respective name defined in configuration.
        """
        return [
            (getattr(policy, "_pyramid_multiauth_name", None), policy)
            for policy in self._policies
        ]

    def get_policy(self, name_or_class):
        """Get one of the contained authentication policies, by name or class.

        This method can be used to obtain one of the subpolicies loaded
        by this policy object.  The policy can be looked up either by the
        name given to it in the config settings, or or by its class.  If
        no policy is found matching the given query, None is returned.

        This may be useful if you need to access non-standard methods or
        properties on one of the loaded policy objects.
        """
        for policy in self._policies:
            if isinstance(name_or_class, basestring):
                policy_name = getattr(policy, "_pyramid_multiauth_name", None)
                if policy_name == name_or_class:
                    return policy
            else:
                if isinstance(policy, name_or_class):
                    return policy
        return None

    def remember(self, request, principal, **kw):
        """Remember the authenticated userid.

        This method returns the concatenation of the headers returned by each
        authn policy.
        """
        headers = []
        for policy in self._policies:
            headers.extend(policy.remember(request, principal, **kw))
        return headers

    def forget(self, request):
        """Forget a previusly remembered userid.

        This method returns the concatenation of the headers returned by each
        authn policy.
        """
        headers = []
        for policy in self._policies:
            headers.extend(policy.forget(request))
        return headers


def append_authorization_principals(request, principals):
    """
    Set principals that are not defined by the authentication.
    """

    try:
        if lookup_tenant(request.db, request.current_tenant_id).get('active') in (
            True,
            None,
        ):
            principals.append(Principals.TenantActive)
        if lookup_tenant(request.db, request.requested_tenant_id).get('active') in (
            True,
            None,
        ):
            principals.append(Principals.RequestedTenantActive)
    except TenantDoesNotExist:
        # We do nothing in this case, we just don't want to set the principal.
        pass

    # decide if this falls under B2B access:
    if (
        request.current_tenant_id != MASTER_TENANT_ID
        and request.requested_tenant_id != request.current_tenant_id
    ):
        principals.append(Principals.B2BAccess)

    # check if someone is accessing master users or the master tenant:
    if request.requested_tenant_id == MASTER_TENANT_ID:
        if isinstance(request.context, User) or isinstance(request.context, Tenants):
            principals.append(Principals.AccessingMasterTenant)

    return principals


def authorization_control_tenant_id(endpoint, info):
    """
    Makes sure tenant ID is controlled by Spynl.
    The tenant ID is added here -and only here-
    to the request filter and data.
    Handle the public documents also.
    TODO: special treatment of master tenant users can go once
          sw-roles are fully migrated.
    """
    if info.options.get('is_error_view', False) is True:
        return endpoint  # no need to control (again)

    def wrapper_view(context, request):
        if request.endpoint_method == 'agg':  # FIXME: remove with /agg
            control_agg_filter(request)
            return endpoint(context, request)

        if request.endpoint_method == 'multi-edit':  # FIXME: remove with /multi-edit
            control_multiedit_filter_and_data(request)
            return endpoint(context, request)

        # control tenant ID in filter and data
        if hasattr(request, 'requested_tenant_id'):
            validate_tenant_id(request.requested_tenant_id)

        is_regular_tenant = request.current_tenant_id != MASTER_TENANT_ID
        if 'filter' in request.args and is_regular_tenant:
            reject_search_by_tenant_id(request.args['filter'])

        if not isinstance(request.context, MongoResource):
            return endpoint(context, request)

        # control mutations of public docs
        if (
            is_regular_tenant
            and request.requested_tenant_id is None
            and request.endpoint_method in ('add', 'edit', 'save', 'import', 'remove')
        ):
            raise IllegalAction(_('not-allowed-public-doc-edit'))
            # TODO: How would we allow to set the tenant to None??

        # Filter by tenant on regular users and when accessing cross tenant endpoints
        if is_regular_tenant or request.requested_tenant_id != MASTER_TENANT_ID:
            request.args['filter'] = extend_filter_by_tenant_id(
                request.args.get('filter', {}),
                [request.requested_tenant_id],  # TODO: pass one ID, not a list
                context,
                include_public=request.endpoint_method in ('get', 'count'),
            )

        # add tenant IDs to data
        if 'data' in request.args:
            if request.endpoint_method in ('add', 'save'):
                # TODO: - this can become a utility method?
                #       - what about the tenants collection?
                for doc in request.args['data']:
                    doc['tenant_id'] = [request.requested_tenant_id]

            if request.endpoint_method == 'edit':

                def edits_tenant(key, value):
                    return key.startswith('$') and 'tenant_id' in value

                if any(
                    edits_tenant(key, value)
                    for key, value in request.args['data'].items()
                ):
                    raise IllegalAction(_('not-allowed-edit-tenant-id'))

        return endpoint(context, request)

    return wrapper_view


authorization_control_tenant_id.options = ('is_error_view',)


def control_agg_filter(request):
    """
    This method encapsulates auth handling for /agg.
    We intend to kill generic /agg but until then, this
    special treatment is needed.
    """
    if request.current_tenant_id != MASTER_TENANT_ID:
        for element in request.args['filter']:
            reject_search_by_tenant_id(element)
        request.args['filter'][0]['$match'] = extend_filter_by_tenant_id(
            request.args['filter'][0]['$match'],
            [request.requested_tenant_id],
            request.context,
        )


def control_multiedit_filter_and_data(request):
    """
    This method encapsulates auth handling for /multi-edit.
    This endpoint allows to send in jobs who each have filter and
    data.
    We intend to kill /multi-edit but until then, this
    special treatment is needed.
    """
    if request.current_tenant_id != MASTER_TENANT_ID:
        jobs = request.args['jobs']
        for job in jobs:
            reject_search_by_tenant_id(job['filter'])
            job['filter'] = extend_filter_by_tenant_id(
                job['filter'], [request.requested_tenant_id], request.context
            )
            for operator in job['data'].keys():
                if 'tenant_id' in job['data'][operator]:
                    raise IllegalAction(_('not-allowed-edit-tenant-id'))
        request.args['jobs'] = jobs

        if request.requested_tenant_id is None:
            raise IllegalAction(_('not-allowed-public-doc-edit'))
