"""
Util functions for spynl.services.pdf.
"""

import os
from sys import platform

from babel.dates import Locale
from babel.dates import format_date as babel_format_date
from babel.dates import format_datetime as babel_format_datetime
from babel.numbers import format_currency as babel_format_currency
from babel.numbers import format_decimal as babel_format_decimal
from jinja2.runtime import Undefined
from marshmallow.fields import Date, DateTime

from spynl.locale import SpynlTranslationString as _


def get_email_settings(user, wholesale=False):
    """
    This is a function in case we need to change things for users with
    multiple tenants.
    """
    # get sender and reply to specifically so they are set to None if they're
    # not in settings
    sender_name = user.get('settings', {}).get('email', {}).get('sender', 'Softwear')
    reply_to = user.get('settings', {}).get('email', {}).get('replyTo')
    body = user.get('settings', {}).get('email', {}).get('body', '')
    subject = user.get('settings', {}).get('email', {}).get('subject')

    if not wholesale:
        # retail settings:
        sender = 'noreply@uwkassabon.nl'
        if not subject:
            subject = _('email-receipt-default-subject').translate()
    else:
        sender = None
        if not subject:
            subject = _('email-receipt-default-subject-wholesale').translate()

    return {
        'sender_name': sender_name,
        'sender': sender,
        'reply_to': reply_to,
        'body': body,
        'subject': subject,
    }


def get_pdf_template_absolute_path(extra_path):
    """
    Get the absolute path of a pdf template.

    This function returns a string path that is compatible
    with all operating systems.

    extra_path parameter is the extension that has to be added
    after ../pdf-templates/
    """
    split_char = '/'

    if platform == 'win32':
        split_char = '\\'
        extra_path.replace('/', '\\')

    path = split_char.join(os.path.abspath(__file__).split(split_char)[:-1])

    return split_char.join([path, 'pdf-templates', extra_path])


def check_value_is_empty(value):
    return value in (None, '') or isinstance(value, Undefined)


def format_datetime(date, format='short', locale='en', tzinfo=None):
    if check_value_is_empty(date):
        return ''
    if isinstance(date, str):
        date = DateTime().deserialize(date)
    return babel_format_datetime(date, format=format, locale=locale, tzinfo=tzinfo)


def format_date(date, format='short', locale='en'):
    if check_value_is_empty(date):
        return ''
    if isinstance(date, str):
        date = Date().deserialize(date)
    return babel_format_date(date, format=format, locale=locale)


def format_country(country, locale='en'):
    """
    country 'NL', locale 'en' returns Netherlands
    country 'NL', locale 'nl' returns Nederland
    """
    if check_value_is_empty(country):
        return ''
    locale = Locale.parse(locale)
    return locale.territories.get(country, country)


def format_currency(value, *args, **kwargs):
    """deal with empty strings"""
    if check_value_is_empty(value):
        return ''
    return babel_format_currency(value, *args, **kwargs)


def format_decimal(value, *args, **kwargs):
    """deal with empty strings"""
    if check_value_is_empty(value):
        return ''
    return babel_format_decimal(value, *args, **kwargs)


def change_case(value, mode='sentence'):
    """
    Properly capitalize the string. Words that are already in upper case should
    not be changed. Available modes:
    sentence: they're bill's friends from the UK -> They're bill's friends from the UK
    title: they're bill's friends from the UK -> They're Bill's Friends From The UK

    The sentence mode assumes there is only one sentence, only the first letter of the
    string is capitalized.
    """
    if not isinstance(value, str):
        return value
    if mode == 'sentence':
        return value[0].upper() + value[1:]
    elif mode == 'title':
        return ' '.join(word[0].upper() + word[1:] for word in value.split())
    else:
        return value


def non_babel_translate(word, language='en'):
    """
    A simple translation function. We use this function instead of the standard
    translation functions, to translate an order based on the language of the
    customer instead of the language of the user. It's also very easy to add another
    language.
    """
    language = language[0:2]
    return TRANSLATIONS.get(word, {}).get(language, word)


TRANSLATIONS = {
    'Order': {
        'nl': 'Order',
        'de': 'Auftrag',
        'fr': 'Commande',
        'es': 'Órdenes',
        'it': 'Ordine',
        'da': 'Ordre',
    },
    'draft': {
        'nl': 'concept',
        'de': 'Entwurf',
        'fr': 'brouillon',
        'es': 'borrador',
        'it': 'bozza',
        'da': 'udkast',
    },
    'Packing List': {
        'nl': 'Pakbon',
        'de': 'Lieferschein',
        'fr': 'Liste de Colisage',
        'es': 'Lista de Empaque',
        'it': 'Lista Imballaggio',
        'da': 'Pakke Liste',
    },
    'Invoice Address': {
        'nl': 'Factuuradres',
        'de': 'Rechnungsanschrift',
        'fr': 'Adresse de Facturation',
        'es': 'Dirección de Facturación',
        'it': 'Indirizzo di Fatturazione',
        'da': 'Faktura Adresse',
    },
    'Delivery Address': {
        'nl': 'Afleveradres',
        'de': 'Lieferadresse',
        'fr': 'Adresse de Livraison',
        'es': 'Dirección de Entrega',
        'it': 'Indirizzo di Consegna',
        'da': 'Leverings Adresse',
    },
    'Payment Terms': {
        'nl': 'Betalingsvoorwaarden',
        'de': 'Zahlungsbedingungen',
        'fr': 'modalités de paiement',
        'es': 'Términos de Pago',
        'it': 'Termini di Pagamento',
        'da': 'Betalingsbetingelser',
    },
    'days': {
        'nl': 'dagen',
        'de': 'Tage',
        'fr': 'journées',
        'es': 'dias',
        'it': 'giorni',
        'da': 'dage',
    },
    'net': {
        'nl': 'netto',
        'de': 'netto',
        'fr': 'net',
        'es': 'neto',
        'it': 'netto',
        'da': 'netto',
    },
    'period': {
        'nl': 'periode',
        'de': 'Zeitraum',
        'fr': 'période',
        'es': 'plazo',
        'it': 'periodo',
        'da': 'tidsrum',
    },
    'Pre-sale discount': {
        'nl': 'Voororderkorting',
        'de': 'Rabatt auf Vorbestellung',
        'fr': 'Remise en pré-commande',
        'es': 'Descuento por adelantado',
        'it': 'Sconto preordine',
        'da': 'Forudbestilling rabat',
    },
    'VAT number': {
        'nl': 'Btw-nummer',
        'de': 'USt-IdNr',
        'fr': 'Numéro de TVA',
        'es': 'Numero de IVA',
        'it': 'Partita IVA',
        'da': 'Moms nummer',
    },
    'Client number': {
        'nl': 'Klantnummer',
        'de': 'Kundennummer',
        'fr': 'Numéro de client',
        'es': 'Número de cliente',
        'it': 'Numero cliente',
        'da': 'Kundenummer',
    },
    'Shipping Carrier': {
        'nl': 'Transporteur',
        'de': 'Lieferant',
        'fr': 'Transporteur',
        'es': 'Transportista de Envío',
        'it': 'Spedizioniere',
        'da': 'Transportør',
    },
    'date': {
        'nl': 'Datum',
        'de': 'Datum',
        'fr': 'date',
        'es': 'fecha',
        'it': 'data',
        'da': 'dato',
    },
    'reservation date': {
        'nl': 'reserveringsdatum',
        'de': 'Datum der Reservierung',
        'fr': 'date de réservation',
        'es': 'fecha de reserva',
        'it': 'data di prenotazione',
        'da': 'reservationsdato',
    },
    'agent': {
        'nl': 'Agent',
        'de': 'Agent',
        'fr': 'agent',
        'es': 'agente',
        'it': 'agente',
        'da': 'agent',
    },
    'price': {
        'nl': 'prijs',
        'de': 'Preis',
        'fr': 'prix',
        'es': 'precio',
        'it': 'prezzo',
        'da': 'pris',
    },
    'total': {
        'nl': 'totaal',
        'de': 'gesamt',
        'fr': 'total',
        'es': 'total',
        'it': 'totale',
        'da': 'total',
    },
    'total number of items': {
        'nl': 'totaal aantal items',
        'de': 'Gesamtzahl der Artikel',
        'fr': "nombre total d'articles",
        'es': 'número total de artículos',
        'it': 'numero totale di articoli',
        'da': 'samlet antal ting',
    },
    'total price': {
        'nl': 'totaalprijs',
        'de': 'Gesamtpreis',
        'fr': 'prix total',
        'es': 'precio total',
        'it': 'prezzo totale',
        'da': 'total pris',
    },
    'Retailprice': {
        'nl': 'Adviesprijs',
        'de': 'Endverbraucherpreis',
        'fr': 'Prix en détail',
        'es': 'Precio al por menor',
        'it': 'Prezzo al dettaglio',
        'da': 'Butikspris',
    },
    'remarks': {
        'nl': 'opmerkingen',
        'de': 'Anmerkungen',
        'fr': 'remarques',
        'es': 'observaciones',
        'it': 'commenti',
        'da': 'bemærkninger',
    },
    # The packing list statuses:
    'pending': {
        'en': 'pending',
        'nl': 'wacht',
        'de': 'anhängig',
        'fr': 'en attente',
        'es': 'pendiente',
        'it': 'in attesa',
    },
    'open': {
        'en': 'open',
        'nl': 'open',
        'de': 'offen',
        'fr': 'ouvert',
        'es': 'abierto',
        'it': 'aperto',
    },
    'picking': {'en': 'being picked', 'nl': 'wordt gepickt'},
    'incomplete': {
        'en': 'incomplete',
        'nl': 'incompleet',
        'de': 'unvollständig',
        'fr': 'incomplet',
        'es': 'incompleto',
        'it': 'incompleto',
    },
    'complete': {
        'en': 'complete',
        'nl': 'compleet',
        'de': 'abgeschlossen',
        'fr': 'complète',
        'es': 'completar',
        'it': 'completa',
    },
    'ready-for-shipping': {
        'en': 'boxed',
        'nl': 'ingepakt',
        'de': 'versandfertig',
        'fr': 'boîte',
        'es': 'en caja',
        'it': 'confezionato',
    },
    'shipping': {'en': 'shipping', 'nl': 'onderweg', 'de': 'versand'},
    'General Terms and Conditions apply to all agreements. By signing this order, '
    'I explicitly declare that I accept your General Terms and Conditions.': {
        'nl': 'Op alle overeenkomsten zijn onze Algemene Voorwaarden van toepassing. '
        'Met het ondertekenen van deze order verklaar ik expliciet dat ik uw '
        'Algemene Voorwaarden accepteer.',
        'es': 'Los Términos y Condiciones Generales se aplican a todos los acuerdos. Al'
        ' firmar este pedido, declaro explícitamente que acepto sus Términos y '
        'Condiciones Generales.',
        'it': 'I termini e le condizioni generali si applicano a tutti gli accordi. '
        'Firmando questo ordine, dichiaro esplicitamente di accettare i tuoi Termini e '
        'Condizioni Generali.',
        'de': 'Für alle Vereinbarungen gelten die Allgemeinen Geschäftsbedingungen. Mit'
        ' der Unterzeichnung dieser Bestellung erkläre ich ausdrücklich, dass ich Ihre '
        'Allgemeinen Geschäftsbedingungen akzeptiere.',
        'fr': "Les conditions générales s'appliquent à tous les accords. En signant "
        "cette commande, je déclare explicitement accepter vos Conditions Générales.",
        'da': 'Generelle vilkår og betingelser gælder for alle aftaler. Ved at '
        'underskrive denne ordre erklærer jeg eksplicit, at jeg accepterer dine '
        'generelle vilkår og betingelser.',
    },
    'The terms and conditions relating to this order are in the attached document.': {
        'nl': 'De voorwaarden voor deze order zijn bijgevoegd in een apart document.',
        'es': 'Los términos y condiciones relativos a este pedido se encuentran en el '
        'documento adjunto.',
        'it': 'I termini e le condizioni relative al presente ordine sono riportati '
        'nel documento allegato.',
        'de': 'Die Bedingungen für diese Bestellung sind in dem beigefügten Dokument '
        'enthalten.',
        'fr': 'Les termes et conditions relatifs à cette commande figurent dans le '
        'document ci-joint.',
        'da': 'Vilkårene og betingelserne for denne ordre findes i vedlagte dokument.',
    },
}
