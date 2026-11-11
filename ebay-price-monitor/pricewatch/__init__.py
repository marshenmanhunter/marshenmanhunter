"""eBay price monitor: track asking prices, likely-sold prices, and flag underpriced listings."""

import warnings

# Apple's built-in Python 3.9 links LibreSSL. urllib3 v2 prints a NotOpenSSLWarning on import,
# yet HTTPS to eBay works. Hide it so real errors stay readable.
warnings.filterwarnings("ignore", message=r"urllib3 v2 only supports OpenSSL")

__version__ = "0.1.0"
