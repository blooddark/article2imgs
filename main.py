from PIL import Image, ImageDraw, ImageFont, ImageColor
import os
import argparse

def wrap_text(text, font, char_spacing, max_width):
    """自动换行处理，考虑字符间距"""
    lines = []
    current_line = []
    current_width = 0
    for char in text:
        if char == '\n':
            if current_line:
                lines.append(''.join(current_line))
                current_line = []
                current_width = 0
            continue
        test_line = current_line + [char]
        test_str = ''.join(test_line)
        str_width = font.getlength(test_str) + char_spacing * (len(test_line) - 1)
        if str_width <= max_width:
            current_line = test_line
            current_width = str_width
        else:
            lines.append(''.join(current_line))
            current_line = [char]
            current_width = font.getlength(char)
    if current_line:
        lines.append(''.join(current_line))
    return lines

def split_into_pages(text, config):
    """将文本分页"""
    try:
        font = ImageFont.truetype(config['font'], config['font_size'])
    except IOError:
        font = ImageFont.load_default()
    
    margins = config['margins']
    page_width, page_height = config['page_size']
    left, top, right, bottom = margins
    available_width = page_width - left - right
    available_height = page_height - top - bottom
    line_height = config['font_size'] + config['line_spacing']
    max_lines = available_height // line_height

    # 处理段落并自动换行
    paragraphs = text.split('\n')
    all_lines = []
    for para in paragraphs:
        if not para.strip():
            continue
        wrapped = wrap_text(para, font, config['char_spacing'], available_width)
        all_lines.extend(wrapped)
        all_lines.append('')  # 段落间空行

    # 分页
    pages = []
    current_page = []
    for line in all_lines:
        if len(current_page) >= max_lines:
            pages.append(current_page)
            current_page = []
        current_page.append(line)
    
    if current_page:
        pages.append(current_page)
    
    return pages

def add_watermark(img, config, page_size):
    """添加水印"""
    if not config or not config.get('text'):
        return
    
    try:
        font = ImageFont.truetype(config['font'], config['font_size']) if config.get('font') else ImageFont.load_default()
    except IOError:
        font = ImageFont.load_default()
    
    text = config['text']
    angle = config.get('angle', 0)
    color = config.get('color', (128, 128, 128, 128))
    position = config.get('position', 'center')
    
    # 创建水印临时图像
    temp_img = Image.new('RGBA', (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    watermark = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)
    draw.text((-bbox[0], -bbox[1]), text, font=font, fill=color)
    
    if angle != 0:
        watermark = watermark.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))
    
    # 计算位置
    img_width, img_height = img.size
    wm_width, wm_height = watermark.size
    # positions = {
    #     'top_left': (100, 100),
    #     'top_right': (img_width - wm_width - 100, 100),
    #     'bottom_left': (10, img_height - wm_height - 10),
    #     'bottom_right': (img_width - wm_width - 10, img_height - wm_height - 10),
    #     'center': ((img_width - wm_width)//2, (img_height - wm_height)//2)
    # }
    # x, y = positions.get(position, (0, 0))
    x, y = (100, 100)
    # 生成多个水印
    for i in range(3):
        for j in range(3):
            img.paste(watermark, (x+i*wm_width+int(i*page_size[0]/3), y+j*wm_height+int(j*page_size[1]/3)), mask=watermark)

def generate_image(page_lines, config, output_path, page_num):
    """生成单页图片"""
    page_width, page_height = config['page_size']
    img = Image.new('RGB', (page_width, page_height), config['bg_color'])
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype(config['font'], config['font_size'])
    except IOError:
        font = ImageFont.load_default()
    
    left, top, right, bottom = config['margins']
    y = top
    line_height = config['font_size'] + config['line_spacing']
    char_spacing = config['char_spacing']
    
    for line in page_lines:
        x = left
        for char in line:
            draw.text((x, y), char, font=font, fill=config['text_color'])
            x += font.getlength(char) + char_spacing
        y += line_height
    
    add_watermark(img, config.get('watermark'), config.get('page_size'))

    # 在底部中间添加页码
    page_text = '- ' + str(page_num) + ' -'
    bbox = draw.textbbox((0, 0), page_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (page_width - text_width) // 2
    y = page_height - bottom - text_height + 50  # 底部边距内显示
    draw.text((x, y), page_text, font=font, fill=config['text_color'])

    img.save(output_path)

def parse_color(color_str):
    """解析颜色字符串"""
    try:
        return ImageColor.getrgb(color_str)
    except ValueError:
        return ImageColor.getrgb('black')

def main():
    parser = argparse.ArgumentParser(description='Generate images from text with watermark.')
    parser.add_argument('input', help='Input text file path')
    parser.add_argument('output_dir', help='Output directory')
    # 文字样式参数
    parser.add_argument('--font', default='./MSYH.TTC', help='Font file path')
    parser.add_argument('--font_size', type=int, default=42, help='Font size')
    # parser.add_argument('--text_color', default='black', help='Text color')
    parser.add_argument('--text_color', default='#eef1f3', help='Text color')
    # parser.add_argument('--bg_color', default='white', help='Background color')
    parser.add_argument('--bg_color', default='#030607', help='Background color')
    parser.add_argument('--line_spacing', type=int, default=30, help='Line spacing')
    parser.add_argument('--char_spacing', type=int, default=2, help='Character spacing')
    parser.add_argument('--margins', type=int, nargs=4, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'), 
                        default=[100, 100, 100, 100], help='Page margins')
    parser.add_argument('--page_size', type=int, nargs=2, metavar=('WIDTH', 'HEIGHT'), 
                        default=[1200, 1600], help='Image dimensions')
    # 水印参数
    parser.add_argument('--watermark_text', help='Watermark text', default='')
    parser.add_argument('--watermark_font', help='Watermark font', default='./MSYH.TTC')
    parser.add_argument('--watermark_font_size', type=int, default=72, help='Watermark font size')
    parser.add_argument('--watermark_color', default='#30303060', help='Watermark color with alpha')
    parser.add_argument('--watermark_position', choices=['top_left', 'top_right', 'bottom_left', 'bottom_right', 'center'], 
                        default='center', help='Watermark position')
    parser.add_argument('--watermark_angle', type=int, default=45, help='Rotation angle')
    
    args = parser.parse_args()
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 读取文本
    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # 构建配置
    config = {
        'font': args.font,
        'font_size': args.font_size,
        'text_color': parse_color(args.text_color),
        'bg_color': parse_color(args.bg_color),
        'line_spacing': args.line_spacing,
        'char_spacing': args.char_spacing,
        'margins': args.margins,
        'page_size': tuple(args.page_size),
        'watermark': {
            'text': args.watermark_text,
            'font': args.watermark_font,
            'font_size': args.watermark_font_size,
            'color': parse_color(args.watermark_color),
            'position': args.watermark_position,
            'angle': args.watermark_angle
        } if args.watermark_text else None
    }
    
    # 分页处理
    pages = split_into_pages(text, config)
    
    # 生成图片
    for i, page in enumerate(pages):
        output_path = os.path.join(args.output_dir, f'page_{i+1:03d}.jpg')
        generate_image(page, config, output_path, i+1)
        print(f'Generated: {output_path}')

if __name__ == '__main__':
    main()