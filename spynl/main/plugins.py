def main(config):
    # NOTE the following is a workaround untill be unify our conftests
    if config.get_settings().get('spynl.tests.no_plugins') == 'true':
        return

    # import in the function to avoid circular imports
    from spynl.api.auth import plugger as auth
    from spynl.api.hr import plugger as hr
    from spynl.api.logistics import plugger as logistics
    from spynl.api.mongo import plugger as mongo
    from spynl.api.retail import plugger as retail

    from spynl.services.pdf import plugger as pdf
    from spynl.services.pipe import plugger as pipe
    from spynl.services.reports import plugger as reports
    from spynl.services.upload import plugger as upload

    # NOTE the order here matters
    config.include(mongo)
    config.include(auth)
    config.include(logistics)
    config.include(hr)
    config.include(retail)

    config.include(pdf)
    config.include(upload)
    config.include(reports)
    config.include(pipe)
