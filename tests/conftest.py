"""Shared fixtures for unit tests."""

import pytest
from bs4 import BeautifulSoup


@pytest.fixture
def make_soup():
    """Factory fixture to create BeautifulSoup from HTML string."""
    return lambda html: BeautifulSoup(html, 'html.parser')


@pytest.fixture
def sample_page_html():
    """A minimal but complete HTML page matching the CCAS site structure."""
    return '''<html>
<head><title>CCAS</title></head>
<body>
<div id="container">
<div id="header"><img src="images/header.jpg"/></div>
<div id="menu">
<a href="index.html">home</a>
<a href="events.html">events</a>
<a href="eat.html">eat</a>
</div>
<div id="content">
<div class="text">
<p>Charm City Art Space is a venue.</p>
</div>
<div id="notes">
<b>Make a general donation to CCAS</b><br/>
Anything you can give is appreciated. We need your help to keep us going.
<form action="https://www.paypal.com/cgi-bin/webscr" method="post">
<input type="hidden" name="cmd" value="_s-xclick"/>
<input type="image" src="https://www.paypalobjects.com/btn_donateCC_LG.gif" alt="PayPal Donate"/>
</form>
</div>
</div>
<div id="footer"><img src="images/footer.jpg"/></div>
</div>
</body>
</html>'''
