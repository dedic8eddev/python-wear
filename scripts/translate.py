"""
Can be used for translation, put the msgid and English translation in the to_translate
variable.
"""

import boto3

translate = boto3.client(
    service_name='translate', region_name='eu-west-1', use_ssl=True
)
target_languages = ['es', 'it', 'de', 'fr']
url = 'https://translation.googleapis.com/language/translate/v2'
to_translate = [
    ('example-key', 'example translation'),
    ('example-key-2', 'Another transalation'),
]
for l in target_languages:  # noqa
    print(l)
    for key, value in to_translate:
        result = translate.translate_text(
            Text=value, SourceLanguageCode="en", TargetLanguageCode=l
        )
        print('msgid "{}"\nmsgstr "{}"\n'.format(key, result.get('TranslatedText')))
