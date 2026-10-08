from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from storage.db import get_db_session

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
