"""
Long-running worker processes for the OmniCare backend.

Workers are separate entry points rather than background tasks in the API process, so
embedding generation and future scheduled work cannot stall a request handler or be
restarted whenever the API scales.
"""
