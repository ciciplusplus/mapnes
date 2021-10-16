from flask import Flask, redirect, send_file
from PIL import Image, ImageStat
import requests
from io import BytesIO

import tempfile
import math
import threading

original_tile_size = 256
small_tile_size = 16

numRows = original_tile_size // small_tile_size

R, G, B = 0, 1, 2

app = Flask(__name__)

tile_grass = Image.open("tiles/tile_grass.png")
tile_forest = Image.open("tiles/tile_forest.png")
tile_water = Image.open("tiles/tile_water.png")
tile_rock = Image.open("tiles/tile_rock.png")
tile_snow = Image.open("tiles/tile_snow.png")
tile_sand = Image.open("tiles/tile_sand.png")

@app.route("/")
def hello_world():
    return app.send_static_file('index.html')

@app.route("/tiles/<int:x>/<int:y>/<int:z>")
def tiles(x, y, z):
    url = "https://khms1.google.com/kh/v=904?x={}&y={}&z={}".format(x, y, z)

    response = requests.get(url)
    img = Image.open(BytesIO(response.content))

    for row in range(numRows):
        for col in range(numRows):
            start_x = col * small_tile_size
            start_y = row * small_tile_size
            rect = (start_x, start_y, start_x + small_tile_size, start_y + small_tile_size)

            stat = ImageStat.Stat(img.crop(rect))

            avgR, avgG, avgB = stat.mean[R], stat.mean[G], stat.mean[B]

            rock_b_threshold = 145
            forest_b_threshold = 65

            if avgR >= 225 and avgG >= 225 and avgB >= 225: # snow
                img.paste(tile_snow, rect)
            elif avgG >= avgB and avgG >= avgR and avgB <= forest_b_threshold: # grass
                img.paste(tile_grass, rect)
            elif avgG >= avgB and avgG >= avgR and avgB > forest_b_threshold: # forest
                img.paste(tile_forest, rect)
            elif avgB >= avgG and avgB >= avgR: # water
                img.paste(tile_water, rect)
            elif avgR >= avgG and avgR >= avgB and avgB <= rock_b_threshold: # sand
                img.paste(tile_sand, rect)
            elif avgR >= avgG and avgR >= avgB and avgB > rock_b_threshold: # rock
                img.paste(tile_rock, rect)
            else:
                pass

    tmpPng = tempfile.NamedTemporaryFile(mode="w+b", delete=False, suffix=".png")
    img.save(tmpPng, 'PNG')
    tmpPng.seek(0)

    return send_file(tmpPng.name, mimetype='image/png')

def serve_pil_image(pil_img):
    img_io = BytesIO()
    pil_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')