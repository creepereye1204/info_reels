# coding: utf-8
import multiprocessing
import os
import random
import time
from datetime import date, datetime
from typing import List

import psutil
import requests
import uvicorn
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Column, Date, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request
from starlette.templating import Jinja2Templates

load_dotenv()
db_host = os.getenv('DB_URL')
templates = Jinja2Templates(directory='info_reels_docker/apps/app/templates')
app = FastAPI()
app.mount('/static',
          StaticFiles(directory='info_reels_docker/apps/app/static'),
          name='static')
pool = None
engine = create_engine(db_host, connect_args={'options': '-c timezone=utc'})
Base = declarative_base()


class InforDao(Base):
    __tablename__ = 'Info'
    info_id = Column(Integer, primary_key=True, autoincrement=True)
    notice = Column(Integer)
    title = Column(String)
    author = Column(String)
    date = Column(Date)
    view = Column(Integer)
    link = Column(String)


Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.commit()
        db.close()


class InforSchema(BaseModel):
    info_id: int
    notice: int
    title: str
    author: str
    date: date
    view: int
    link: str

    class Config:
        from_attributes = True


def crawling():
    MINUTE = 60
    random_min = 10
    random_max = 20
    start_index = 1
    end_index = 10
    db = SessionLocal()
    while True:
        try:
            db.query(InforDao).delete()
            for index in range(start_index, end_index):
                url = 'https://www.syu.ac.kr/academic/academic-notice/page/' \
                      f'{index}/'
                response = requests.get(url)
                html = response.content.decode('utf-8')
                soup = BeautifulSoup(html, 'html.parser')
                notices = soup.findAll('th', class_='step1')
                titles = soup.findAll('span', class_='tit')
                authors = soup.findAll('td', class_='step3')
                dates = soup.findAll('td', class_='step4')
                views = soup.findAll('td', class_='step6')
                links = soup.findAll('td', class_='step2')

                for elements in zip(notices, titles, authors, dates, views,
                                    links):
                    notice, title, author, date, view, link = elements
                    date_obj = datetime.strptime(
                        date.text.strip(),
                        '%Y.%m.%d').date()  # 날짜 문자열을 datetime.date 객체로 변환
                    notice = notice.text.strip()
                    infor = InforDao(
                        notice=int(notice) if notice.isdigit() else 9999999,
                        title=title.text.strip(),
                        author=author.text.strip(),
                        date=date_obj,  # 변환된 date 객체 사용
                        view=int(view.text.strip().replace(',', '')),
                        link=link.find('a', class_='itembx')['href'])
                    db.add(infor)
        except Exception as e:
            print(f'Error occurred: {e}')
            db.rollback()
        finally:
            db.commit()
            db.close()
        time.sleep(MINUTE * random.randint(random_min, random_max))


@app.get('/items', response_model=List[InforSchema])
async def read_items(request: Request, db: Session = Depends(get_db)):
    items = db.query(InforDao).all()
    items.sort(reverse=True, key=lambda x: (x.notice, x.date))
    return templates.TemplateResponse(request, 'board.html', {'items': items})


@app.get('/')
async def get_settings(request: Request):
    return templates.TemplateResponse(request, 'home.html',
                                      {'request': request})


@app.get('/dashboard')
def get_usage_data():
    cpu_usage = round(psutil.cpu_percent(interval=1), 2)
    hdd_usage = round(psutil.disk_usage('/').percent, 2)
    mem_usage = round(psutil.virtual_memory().percent, 2)

    return {
        'cpu_usage': cpu_usage,
        'hdd_usage': hdd_usage,
        'mem_usage': mem_usage
    }


@app.on_event('startup')
async def start_crawling():
    global pool
    pool = multiprocessing.Pool(processes=1)
    pool.apply_async(crawling)


@app.on_event('shutdown')
async def stop_crawling():
    global pool
    if pool:
        pool.terminate()
        pool.join()
        pool = None
        print('Stopped')


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)
