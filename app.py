from flask import Flask, redirect, send_file
from PIL import Image, ImageStat
import requests
from io import BytesIO

import tempfile
import math
import mapnik
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

def minmax (a,b,c):
    a = max(a,b)
    a = min(a,c)
    return a

class GoogleProjection:
    def __init__(self,levels=18):
        self.Bc = []
        self.Cc = []
        self.zc = []
        self.Ac = []
        c = 256
        for d in range(0,levels):
            e = c/2;
            self.Bc.append(c/360.0)
            self.Cc.append(c/(2 * math.pi))
            self.zc.append((e,e))
            self.Ac.append(c)
            c *= 2

    def fromLLtoPixel(self,ll,zoom):
        d = self.zc[zoom]
        e = round(d[0] + ll[0] * self.Bc[zoom])
        f = minmax(math.sin(math.radians(ll[1])),-0.9999,0.9999)
        g = round(d[1] + 0.5*math.log((1+f)/(1-f))*-self.Cc[zoom])
        return (e,g)

    def fromPixelToLL(self,px,zoom):
        e = self.zc[zoom]
        f = (px[0] - e[0])/self.Bc[zoom]
        g = (px[1] - e[1])/-self.Cc[zoom]
        h = math.degrees( 2 * math.atan(math.exp(g)) - 0.5 * math.pi)
        return (f,h)

m = mapnik.Map(original_tile_size, original_tile_size)
mapnik.load_map(m, "labels.xml")
prj = mapnik.Projection(m.srs)
maxZoom = 20
tileproj = GoogleProjection(maxZoom + 1)

lock = threading.Lock()

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

    tmpPng2 = tempfile.NamedTemporaryFile(mode="w+b", delete=False, suffix=".png")
    return render_tile(tmpPng.name, tmpPng2.name, x, y, z)

def serve_pil_image(pil_img):
    img_io = BytesIO()
    pil_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

def render_tile(back_img, tile_handle, x, y, z):
    # Calculate pixel positions of bottom-left & top-right
    p0 = (x * 256, (y + 1) * 256)
    p1 = ((x + 1) * 256, y * 256)

    # Convert to LatLong (EPSG:4326)
    l0 = tileproj.fromPixelToLL(p0, z);
    l1 = tileproj.fromPixelToLL(p1, z);

    # Convert to map projection (e.g. mercator co-ords EPSG:900913)
    c0 = prj.forward(mapnik.Coord(l0[0],l0[1]))
    c1 = prj.forward(mapnik.Coord(l1[0],l1[1]))

    # Bounding box for the tile
    bbox = mapnik.Box2d(c0.x, c0.y, c1.x, c1.y)

    render_size = 256

    with lock:
        m.resize(render_size, render_size)
        m.zoom_to_box(bbox)
        m.buffer_size = 128

        # Render image with default Agg renderer
        im = mapnik.Image(render_size, render_size)
        m.background_image = back_img
        mapnik.render(m, im)
        im.save(tile_handle, 'png256')

        return send_file(tile_handle, mimetype='image/png')