# Helper script to run Alembic commands with correct Python path
# Usage: .\run-alembic.ps1 current
#        .\run-alembic.ps1 upgrade head
#        .\run-alembic.ps1 history

python -m alembic $args
