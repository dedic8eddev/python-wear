""" Tests for contact.py """


def test_contact_us(app, inbox):
    """Test the contact us endpoint"""
    payload = {
        'email': 'someone@blah.com',
        'name': 'Someone Something',
        'subject': 'A question',
        'message': 'Can you mail me back?',
        'category': 'retail',
        'phone': '123-456789',
    }
    app.post_json('/contact-us', payload, status=200)
    assert inbox[0].subject == 'SoftwearConnect contact form: {}'.format(
        payload['subject']
    )
    assert inbox[0].recipients == ['marketing@softwear.nl']
    assert inbox[0].body.data == (
        'E-mail: someone@blah.com\n\n'
        'Name: Someone Something\n\n'
        'Phonenumber: 123-456789\n\n'
        'Category: retail\n\n'
        'Message:\n\n'
        'Can you mail me back?   \n  \n'
        '[ ](https://www.softwearconnect.com)\n'
    )
    assert inbox[0].extra_headers == {'Reply-To': 'someone@blah.com'}
