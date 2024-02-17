import time, math, framebuf, random
from machine import Pin, SPI, freq
from lib import st7789py
from misc import ttoast_bitmaps as toast_bitmaps

tft = st7789py.ST7789(
    SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), miso=None),
    135,
    240,
    reset=Pin(33, Pin.OUT),
    cs=Pin(37, Pin.OUT),
    dc=Pin(34, Pin.OUT),
    backlight=Pin(38, Pin.OUT),
    rotation=1,
    color_order=st7789py.BGR
    )

fbuf = framebuf.FrameBuffer(bytearray(240*135*2), 240, 135, framebuf.RGB565)

TOASTER_FRAMES = [0, 1, 2, 3]
TOAST_FRAMES = [4]
BLACK = const(0x0000)

def bitmap_to_framebuf(bitmap, x, y, index=0):
    """
    MODIFIED FROM st7789py!
    Draw a bitmap on display at the specified column and row

    Args:
        bitmap (bitmap_module): The module containing the bitmap to draw
        x (int): column to start drawing at
        y (int): row to start drawing at
        index (int): Optional index of bitmap to draw from multiple bitmap
            module
    """
    width = bitmap.WIDTH
    height = bitmap.HEIGHT
    to_col = x + width - 1
    to_row = y + height - 1

    bitmap_size = height * width
    buffer_len = bitmap_size * 2
    bpp = bitmap.BPP
    bs_bit = bpp * bitmap_size * index  # if index > 0 else 0
    palette = bitmap.PALETTE
    needs_swap = False
    buffer = bytearray(buffer_len)

    for i in range(0, buffer_len, 2):
        color_index = 0
        for _ in range(bpp):
            color_index = (color_index << 1) | (
                (bitmap.BITMAP[bs_bit >> 3] >> (7 - (bs_bit & 7))) & 1
            )
            bs_bit += 1

        color = palette[color_index]
        if needs_swap:
            buffer[i] = color & 0xFF
            buffer[i + 1] = color >> 8
        else:
            buffer[i] = color >> 8
            buffer[i + 1] = color & 0xFF

    #tft._set_window(x, y, to_col, to_row)
    #tft._write(None, buffer)
    return framebuf.FrameBuffer(buffer, width, height, framebuf.RGB565)
     
def collide(a_col, a_row, a_width, a_height, b_col, b_row, b_width, b_height):
    """return true if two rectangles overlap"""
    return (
        a_col + a_width >= b_col
        and a_col <= b_col + b_width
        and a_row + a_height >= b_row
        and a_row <= b_row + b_height
    )


def random_start(tft, sprites, bitmaps, num):
    """
    Return a random location along the top or right of the screen, if that location would overlaps
    with another sprite return (0,0). This allows the other sprites to keep moving giving the next
    random_start a better chance to avoid a collision.

    """
    # 50/50 chance to try along the top/right half or along the right/top half of the screen
    if random.getrandbits(1):
        row = 1
        col = random.randint(bitmaps.WIDTH // 2, tft.width - bitmaps.WIDTH)
    else:
        col = tft.width - bitmaps.WIDTH
        row = random.randint(1, tft.height // 2)

    if any(
        collide(
            col,
            row,
            bitmaps.WIDTH,
            bitmaps.HEIGHT,
            sprite.col,
            sprite.row,
            sprite.width,
            sprite.height,
        )
        for sprite in sprites
        if num != sprite.num
    ):

        col = 0
        row = 0

    return col, row


def main():
    
    # create framebufs with the animation frames
    frame_bufs = []
    
    for i in range(0,5):
        frame_bufs.append( bitmap_to_framebuf(toast_bitmaps, 0, 0, i) )
        
    class Toast:
        """
        Toast class to keep track of toaster and toast sprites
        """

        def __init__(self, sprites, bitmaps, frames):
            """create new sprite in random location that does not overlap other sprites"""
            self.num = len(sprites)
            self.bitmaps = bitmaps
            self.frames = frames
            self.steps = len(frames)
            self.col, self.row = random_start(tft, sprites, bitmaps, self.num)
            self.width = bitmaps.WIDTH
            self.height = bitmaps.HEIGHT
            self.last_col = self.col
            self.last_row = self.row
            if self.steps == 1:
                self.step = 4
            else:
                self.step = random.randint(0, self.steps)
            self.dir_col = -random.randint(2, 5)
            self.dir_row = 2
            self.prev_dir_col = self.dir_col
            self.prev_dir_row = self.dir_row
            self.iceberg = 0

        def move(self, sprites):
            """step frame and move sprite"""

            if self.steps > 1:
                self.step = (self.step + 1) % self.steps

            self.last_col = self.col
            self.last_row = self.row
            new_col = self.col + self.dir_col
            new_row = self.row + self.dir_row

            # if new location collides with another sprite, change direction for 32 frames

            for sprite in sprites:
                if (
                    self.num != sprite.num
                    and collide(
                        new_col,
                        new_row,
                        self.width,
                        self.height,
                        sprite.col,
                        sprite.row,
                        sprite.width,
                        sprite.height,
                    )
                    and (self.col > sprite.col)
                ):

                    self.iceberg = 32
                    self.dir_col = -1
                    self.dir_row = 3
                    new_col = self.col + self.dir_col
                    new_row = self.row + self.dir_row

            self.col = new_col
            self.row = new_row

            # if new location touches edge of screen, erase then set new start location
            if self.col <= 0 or self.row + self.height > tft.height:
                self.dir_col = -random.randint(2, 5)
                self.dir_row = 2
                self.col, self.row = random_start(tft, sprites, self.bitmaps, self.num)

            # Track post collision direction change
            if self.iceberg:
                self.iceberg -= 1
                if self.iceberg == 1:
                    self.dir_col = self.prev_dir_col
                    self.dir_row = self.prev_dir_row

        def draw(self):
            """if the location is not 0,0 draw current frame of sprite at it's location"""
            if self.col and self.row:
                #bitmap(tft, fbuf, self.bitmaps, self.col, self.row, self.frames[self.step])
                fbuf.blit(frame_bufs[self.step], self.col, self.row)
    try:

        # create toast spites and set animation frames
        sprites = []

        sprites.append(Toast(sprites, toast_bitmaps, TOAST_FRAMES))
        sprites.append(Toast(sprites, toast_bitmaps, TOASTER_FRAMES))
        sprites.append(Toast(sprites, toast_bitmaps, TOAST_FRAMES))
        sprites.append(Toast(sprites, toast_bitmaps, TOASTER_FRAMES))
        sprites.append(Toast(sprites, toast_bitmaps, TOASTER_FRAMES))

        # move and draw sprites

        while True:
            fbuf.fill(BLACK)
            
            for sprite in sprites:
                sprite.move(sprites)
                sprite.draw()
            
            tft.blit_buffer(fbuf, 0,0,240,135)
            gc.collect()
            time.sleep_ms(10)

    finally:
        print("done")


main()