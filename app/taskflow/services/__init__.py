"""Business rules, callable and testable without HTTP.

Services validate input, enforce the workflow and own their transactions.
They raise the domain errors in :mod:`taskflow.services.errors`; mapping
those to status codes is the API layer's job.
"""
