from fastapi import APIRouter

router = APIRouter(prefix="/farmers", tags=["farmers"])

# Farmer self-signup removed — farmers are created by admin only.
# See POST /admin/farmers for the current flow.
