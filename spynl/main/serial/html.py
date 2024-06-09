"""If needed, Spynl can return an HTML response."""

DOCTYPE = '<!DOCTYPE html>'


def dumps(content, pretty=False):
    """format an HTML response"""
    if not content.lstrip().startswith("<!DOCTYPE"):
        content = DOCTYPE + content
    return content
