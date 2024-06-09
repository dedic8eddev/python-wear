"""Configuration for session factory"""

from spynl.main.exceptions import SpynlException
from spynl.main.utils import get_parsed_body


def main(config):
    """
    * Configure which session factory to use, pyramid's default or one that
      is set in the auth plugin.
    """
    settings = config.get_settings()
    # This if/else statement can be removed when all plugins are always loaded.
    if 'MongoDB' not in settings:
        from beaker.session import Session

        def mksession(sid):
            return Session(None, id=sid, use_cookies=False)

    else:
        Session = settings['MongoDB']
        if not Session:
            msg = (
                'The function for the session factory is not set in any of the plugins.'
            )
            raise SpynlException(msg)

        def mksession(sid):
            return Session(id=sid)

    def session_factory(request):
        """We keep one session per sid"""
        sid = None
        # getting the sid from request.args would be easier,
        # but we cannot rely on args being unified there already.
        # We look for a session ID (sid) with decreasing priority in
        # cookies, headers, GET vars, POST vars.
        try:
            body = get_parsed_body(request)
        except:  # noqa: E722
            body = {}
        for params in (body, request.GET, request.headers, request.cookies):
            if 'sid' in params:
                sid = params['sid']

        return mksession(sid)

    config.set_session_factory(session_factory)

    def new_response(event):
        """
        Make sure new and pristine sessions are saved.
        Changes to sessions should save them automatically
        and set session.new to False.
        """
        session = event.request.session
        if session:
            if hasattr(session, 'new'):
                if session.new is True:
                    session.save()
            else:
                session.save()

    config.add_subscriber(new_response, 'pyramid.events.NewResponse')
