"""
Tests for mail functionality in spynl.main.

Tests that need a real email template, create one temporary run the test and
then delete it.
Wherever needed, try to rename the default template in order exceptions to be
raised and after test runs rename again the default template to its original
name.
"""


from uuid import uuid4

import pytest
from pyramid.testing import DummyRequest

from spynl.main.exceptions import EmailTemplateNotFound
from spynl.main.mail import _sendmail as sendmail
from spynl.main.mail import send_template_email


@pytest.fixture
def template(tmpdir):
    """Create a temporary template file for tests to use."""
    name = uuid4().hex
    folder = tmpdir.mkdir('template')
    file_ = folder.join(name + '.jinja2')
    subject_ = folder.join(name + '.subject.jinja2')
    yield (file_.strpath, subject_.strpath)


@pytest.fixture
def dummy_request():
    """Return a testing DummyRequest for tests to use."""
    dummy_request = DummyRequest()
    return dummy_request


def test_simple_plain_email(dummy_request, mailer):
    """Do a simple plain email test"""
    assert sendmail(
        dummy_request,
        'nicolas@softwear',
        'Nic Test',
        "Hey Nic! It's me, Nic.",
        mailer=mailer,
    )
    email = mailer.outbox[0]
    assert email.subject == 'Nic Test'
    assert email.body == "Hey Nic! It's me, Nic."


def test_sender_name(dummy_request, mailer):
    """
    test that the sender_name gets added and that any problematic characters are
    removed.
    """
    assert sendmail(
        dummy_request,
        'nicolas@softwear',
        'Nic Test',
        "Hey Nic! It's me, Nic.",
        sender_name='<bla@bla.com\n bla>',
        mailer=mailer,
    )
    email = mailer.outbox[0]
    assert email.extra_headers == {'From': 'bla bla.com  bla <info@spynl.com>'}


def test_bcc(dummy_request, mailer):
    """
    test that bcc gets added properly
    """
    assert sendmail(
        dummy_request,
        'nicolas@softwear',
        'Nic Test',
        "Hey Nic! It's me, Nic.",
        bcc=['bcc@bcc.com', 'bcc2@bcc.com'],
        mailer=mailer,
    )
    email = mailer.outbox[0]
    assert email.bcc == ['bcc@bcc.com', 'bcc2@bcc.com']


def test_cc(dummy_request, mailer):
    """
    test that cc gets added properly
    """
    assert sendmail(
        dummy_request,
        'nicolas@softwear',
        'Nic Test',
        "Hey Nic! It's me, Nic.",
        cc=['cc@cc.com', 'cc2@cc.com'],
        mailer=mailer,
    )
    email = mailer.outbox[0]
    assert email.cc == ['cc@cc.com', 'cc2@cc.com']


def test_custom_html_template_mail(dummy_request, mailer, template):
    """The custom template is correctly used."""
    with open(template[0], 'w') as fob:
        fob.write(
            '''<!--CUSSSTOM-->
                     <p>Hey Nic!</p><p>It's me, Nic</p>
                     <p><a href={url}>{url}</a></p>'''.format(
                url='http://spynl.softwearconnect.com'
            )
        )
    with open(template[1], 'w') as fob2:
        fob2.write('{{"Nic Test"}}')
    assert send_template_email(
        dummy_request,
        'nicolas@softwear',
        template_file=template[0].replace('.jinja2', ''),
        replacements={},
        mailer=mailer,
        sender='blah@blah.com',
    )
    email = mailer.outbox[0]
    assert email.subject == 'Nic Test'
    assert "<p>Hey Nic!</p>" in email.html.data
    assert "<p>It's me, Nic</p>" in email.html.data
    assert (
        "<p><a href={url}>{url}</a></p>".format(url='http://spynl.softwearconnect.com')
        in email.html.data
    )
    assert "<!--CUSSSTOM-->" in email.html.data
    assert email.sender == 'blah@blah.com'


def test_custom_jinja_expressions_template_mail(dummy_request, mailer, template):
    """The custom jinja template is correctly used, both in subject and body"""
    replacements = {
        'subject_content': 'replaced subject content',
        'content': 'replaced content',
        'nested_content': {'child': 'I is child content'},
    }
    with open(template[0], 'w') as fob:
        fob.write('aaa ---{{content}}--- bbb')
        fob.write('aaa ---{{nested_content["child"]}}--- bbb')
        fob.write('bbb ---{{50 + 50}}--- aaa')
    with open(template[1], 'w') as fob:
        fob.write('{{ "EMAIL SUBJECT: " + subject_content }}\n')
    send_template_email(
        dummy_request,
        'test_recipient_1',
        template_file=template[0].replace('.jinja2', ''),
        replacements=replacements,
        subject='',
        mailer=mailer,
    )
    assert mailer.outbox[0].subject == 'EMAIL SUBJECT: replaced subject content'
    assert (
        'aaa ---replaced content--- bbbaaa ---I is child content--- bbb'
        'bbb ---100--- aaa'
    ) in mailer.outbox[0].html.data


def test_custom_jinja_control_logic_template_mail(dummy_request, mailer, template):
    """Jinja control logic is handled in subject and body"""
    replacements = dict(a=True, b=[1, 2, 3])
    with open(template[0], 'w') as fob:
        fob.write(
            '''{% if a %}\nI saw A.\n{% else %}\nI did not see A.\n{% endif %}
               {% for i in b %}\nI:{{i}}\n {% endfor %}'''
        )
    with open(template[1], 'w') as fob:
        fob.write('{{"I saw A."}}')
    send_template_email(
        dummy_request,
        'test_recipient_1',
        template_file=template[0].replace('.jinja2', ''),
        replacements=replacements,
        mailer=mailer,
    )
    assert mailer.outbox[0].subject == 'I saw A.'
    for val in ("I:1", "I:2", "I:3"):
        assert val in mailer.outbox[0].html.data


def test_send_template_email_with_string_as_template(dummy_request, mailer):
    """Successful use of template string instead of template file"""
    replacements = {'bla': 'some content'}
    template_string = 'Here is {bla}'.format(**replacements)
    send_template_email(
        dummy_request,
        'recipient',
        template_string=template_string,
        mailer=mailer,
        sender='sender',
    )
    email = mailer.outbox[0]
    assert email.subject == ''
    assert email.sender == 'sender'
    assert 'Here is some content' in email.body.data


def test_send_template_email_with_empty_recipient(dummy_request, mailer):
    """Empty recipient should not be allowed."""
    assert not send_template_email(
        dummy_request, '', template_string='', replacements={}, mailer=mailer
    )


def test_send_template_email_with_none_recipient(dummy_request, mailer):
    """Recipient with None value should not be allowed."""
    assert not send_template_email(
        dummy_request, None, template_string='', replacements={}, mailer=mailer
    )


def test_send_template_email_with_empty_subject(dummy_request, mailer, template):
    """Subject has to be given explicitly."""
    with open(template[0], 'w') as fob:
        fob.write('\n')
        fob.write('test body')
    with open(template[1], 'w') as fob:
        fob.write('\n')
    send_template_email(
        dummy_request,
        'test_recipient',
        template_file=template[0].replace('.jinja2', ''),
        replacements={},
        mailer=mailer,
    )
    assert mailer.outbox[0].subject == ''


def test_send_template_email_when_template_doesnt_exist(dummy_request, mailer):
    """When no template is found, default one should be used."""
    with pytest.raises(EmailTemplateNotFound):
        send_template_email(
            dummy_request,
            'test_recipient',
            template_file='/random/template/path/file',
            replacements={},
            mailer=mailer,
        )
    assert mailer.outbox == []


def test_send_template_email_when_template_exists(dummy_request, mailer, template):
    """Ensure that the existent template will be used instead of default."""
    with open(template[0], 'w') as fob:
        fob.write('aaa ---{{extra_content}}--- bbb')
    with open(template[1], 'w') as fob:
        fob.write('{{"FIRST EMAIL SUBJECT" }}\n')
    replacements = {'extra_content': 'Some replacement to be replaced.'}
    send_template_email(
        dummy_request,
        'test_recipient_1',
        template_file=template[0].replace('.jinja2', ''),
        replacements=replacements,
        mailer=mailer,
    )
    assert mailer.outbox[0].subject == 'FIRST EMAIL SUBJECT'
    assert (
        'aaa ---Some replacement to be replaced.--- bbb' in mailer.outbox[0].html.data
    )


def test_send_template_email_with_non_ascii_character(dummy_request, mailer, tmpdir):
    """Non ascii characters should be encoded to UTF-8."""
    folder = tmpdir.mkdir('sub')
    temp_file = folder.join('my_template.jinja2')
    temp_subject = folder.join('my_template.subject.jinja2')
    temp_file.write("ⓢⓢⓢ".encode(), mode='wb')
    temp_subject.write("{{ 'subject' }}", mode='w')
    send_template_email(
        dummy_request,
        'recipient',
        template_file=temp_file.strpath.replace('.jinja2', ''),
        subject='test subject',
        mailer=mailer,
        sender='sender',
    )
    assert 'ⓢⓢⓢ' in mailer.outbox[0].body.data
