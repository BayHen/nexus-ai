"""Application composition root package.

Import concrete entry points from their modules so worker configuration can load
without importing the FastAPI application and its route graph.
"""
