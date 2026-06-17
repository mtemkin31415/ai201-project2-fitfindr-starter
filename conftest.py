"""
Root conftest.py — ensures the project root is on sys.path so tests can do
`from tools import ...` regardless of where pytest is invoked from.

Its mere presence at the project root makes pytest add this directory to
sys.path during collection, so no extra code is required here.
"""
