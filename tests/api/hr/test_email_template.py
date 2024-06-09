""" Test the email template and it's replacements function """

import pytest

from spynl.api.auth.testutils import mkuser


@pytest.fixture
def set_db(db):
    """Populate database with data."""
    db.tenants.insert_one(
        {
            '_id': 'tenant_with_logo',
            'name': 'tenant with logo',
            'settings': {'logoUrl': {'medium': 'http://logo.bla'}},
        }
    )

    db.tenants.insert_one({'_id': 'tenant_without_logo', 'name': 'tenant without logo'})

    mkuser(db, 'user1', 'blah', ['tenant_with_logo', 'tenant_without_logo'])


@pytest.mark.parametrize('login', [('user1', 'blah')], indirect=True)
def test_email_footer_contains_softwear_logo(set_db, app, mailer_outbox, login):
    """Softwear logo is served from spynl.hr and exist in all emails."""
    payload = {'new_email': 'bla@test.com', 'current_pwd': 'blah'}
    app.post_json('/change-email', payload, status=200)
    email = mailer_outbox[0]
    assert (
        ' src="https://s3-eu-west-1.amazonaws.com/softwear-static-assets/'
        'SoftwearPoweredBy.png"'
    ) in email.html.data


@pytest.mark.parametrize('login', [('user1', 'blah')], indirect=True)
def test_dutch_email_template(set_db, app, mailer_outbox, login):
    """Ensure Dutch version is picked up if locale is nl."""
    payload = {'new_email': 'bla@test.com', 'current_pwd': 'blah'}
    app.post_json(
        '/change-email', payload, status=200, headers={'Accept-Language': 'nl-NL'}
    )
    email = mailer_outbox[0]
    assert (
        'Beste Mister user1, \n\n'
        'Het e-mailadres voor gebruiker user1 is zojuist gewijzigd van dit '
        'e-mailadres naar bla@test.com. \n\n'
        'Als u dit niet zelf heeft gedaan, bestaat de mogelijkheid dat '
        'iemand het e-mailadres zonder uw toestemming heeft gewijzigd. '
        'Neem dan direct contact op met onze servicedesk via '
        '[https://www.softwearconnect.com/#/support]'
        '(https://www.softwearconnect.com/#/support)\n\n'
        'Met vriendelijke groet, \n\n'
        'het Softwear Team   \n  \n'
        '[ ](https://www.softwearconnect.com)\n'
    ) in email.body.data


@pytest.mark.parametrize('login', [('user1', 'blah')], indirect=True)
def test_link_is_escaped_in_email_when_requesting_pwd_reset(
    set_db, app, mailer_outbox, db, login
):
    """Ensure link is escaped."""
    app.post_json('/request-pwd-reset', dict(username='user1'), status=200)
    user = db.users.find_one({'username': 'user1'})
    key = user['keys']['pwd_reset']['key']
    email = mailer_outbox[0]
    assert '?username={}&key={}'.format('user1', key) in email.body.data


@pytest.mark.skip(reason="not added yet in the plugger")
@pytest.mark.parametrize('login', [('user1', 'blah')], indirect=True)
def test_link_is_escaped_in_email_when_resend_email_verification(
    set_db, app, db, mailer_outbox, login
):
    """Ensure link is escaped."""
    db.users.update_one({'username': 'user1'}, {'$set': {'email_verify_pending': True}})
    app.post_json('/resend-email-verification-key', status=200)
    user = db.users.find_one({'username': 'user1'})
    user_email = user['email']
    user_key = user['keys']['email-verification']['key']
    email = mailer_outbox[0]
    assert '?email={}&key={}'.format(user_email, user_key) in email.body


@pytest.mark.parametrize('login', [('user1', 'blah')], indirect=True)
def test_link_is_escaped_in_email_when_changing_email(
    set_db, app, db, mailer_outbox, patch_dns_resolver, login
):
    """Ensure link is escaped."""
    payload = dict(current_pwd='blah', new_email='foo@bar.com')
    app.post_json('/change-email', payload, status=200)

    user = db.users.find_one({'username': 'user1'})
    user_key = user['keys']['email-verification']['key']
    email = mailer_outbox[1]
    assert '?email={}&key={}'.format('foo%40bar.com', user_key) in email.body.data


def test_support_url_html_is_escaped_in_change_ownership_template(
    set_db, app, db, mailer_outbox
):
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    mkuser(db, 'user2', 'blah', ['master'], tenant_roles=dict(master=['sw-admin']))
    app.get('/login', dict(username='user2', password='blah'))

    app.post_json(
        '/tenants/tenant_without_logo/tenants/change-ownership',
        dict(username='user1', is_owner=True),
    )

    support_url = "https://www.softwearconnect.com/#/support"
    html = '<a href="{}">{}</a>'.format(support_url, support_url)
    assert html in mailer_outbox[0].html.data
