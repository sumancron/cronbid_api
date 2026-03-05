from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from routes import include_all_routes
from database import Database

origins = [
      "https://ads.cronbid.com",
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

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/campaignsmedia", StaticFiles(directory="uploads/campaignsmedia"), name="campaignsmedia")

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.get("/sourcedocs", response_class=HTMLResponse)
async def read_root():
    with open("docs.html", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())