"""
Translation logic.
Kept in its own module so it can be imported by any Spynl code.
"""
from pyramid import threadlocal
from pyramid.i18n import TranslationString
from pyramid_jinja2.i18n import GetTextWrapper


class SpynlTranslationString(object):
    """
    A wrapper class around a Pyramid TranslationString.

    This class contains an entry for a Pyramid TranslationString
    (self.translation_string), and determines the domain for the string during
    initialization.

    Why we implement this:
    During serialisation, the json encoder recognizes a TranslationString as a
    str, and treats it accordingly. This means that it takes the immutable
    string that is made during creation of the TranslationString, which
    corresponds to the msgid. There is no way to overwrite this behaviour, by
    inheriting the TranslationString class itself.
    Because we have a class here that inherits from object, we can add a
    custom encoder for this class to supplement the JSONEncoder.
    """

    # TODO: should we add __slots__ = ('translation_string')?
    def __init__(self, msgid, default=None, mapping=None, context=None):
        """
        Initialize a TranslationString, using the correct domain.
        """
        # loop over mapping dictionary to check for translation strings:
        # (In principle mappings shouldn't be translation strings, but this
        #  may be unavoidable when e.g. a broad exception gets a more detailed
        #  message from the code that raises it)
        if mapping:
            for key in mapping:
                if isinstance(mapping[key], SpynlTranslationString):
                    mapping[key] = mapping[key].translate()
        # Initialize a Pyramid TranslationString
        self.translation_string = TranslationString(
            msgid, default=default, mapping=mapping, context=context, domain='spynl'
        )

    def __repr__(self):
        """
        Return 'msgid: interpolated string'
        """
        # TODO: maybe we should include the mapping and default explicitly
        # instead of in the interpolated message.
        msgid = str(self.translation_string)
        message = self.translation_string.interpolate()
        return '{}: {}'.format(msgid, message)

    def __str__(self):
        """
        Return the interpolated default string.
        """
        return self.translation_string.interpolate()

    def translate(self, localizer=None):
        """Translate the translation string using the provided localizer."""
        # We prefer to get the localizer from the place where the string gets
        # tranlated, but in some places, that adds too much code (e.g. in
        # exceptions that need to translate a translation string before adding
        # it to another translation string in a mapping.
        if not localizer:
            request = threadlocal.get_current_request()
            if request is None:  # we cannot find out locale of the user, so
                return str(self)  # we'll use the interpolated default
            else:
                localizer = request.localizer
        return localizer.translate(self.translation_string)


class TemplateTranslations(GetTextWrapper):
    """Translate in templates using the spynl translation string"""

    def gettext(self, *args, **kwargs):
        """Implements jinja.ext.i18n `gettext` function."""
        translation_string = SpynlTranslationString(*args, **kwargs)
        return translation_string.translate(self.localizer)
