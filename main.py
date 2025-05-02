from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routes import include_all_routes
from database import Database

origins = [
    "https://ads.cronbid.com",  # no trailing slash
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.connect()
    yield
    await Database.close()

app = FastAPI(
    title="Cronbid API",
    debug=True,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

include_all_routes(app)

@app.get("/")
async def read_root():
    return {"Hello": "World"}
