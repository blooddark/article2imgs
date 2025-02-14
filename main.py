from PIL import Image, ImageDraw, ImageFont, ImageColor
import os
import argparse
import random
import re

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
    """将文本分页，使用背景颜色生成图片时的原始处理逻辑"""
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
    """添加水印 (原来模式：用纯色背景生成图片时调用)"""
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
    
    # 固定位置示例，此处可根据需要调整
    img_width, img_height = img.size
    wm_width, wm_height = watermark.size
    x, y = (100, 100)
    # 生成多个水印
    for i in range(3):
        for j in range(3):
            img.paste(watermark, (x+i*wm_width+int(i*page_size[0]/3), y+j*wm_height+int(j*page_size[1]/3)), mask=watermark)

def generate_image(page_lines, config, output_path, page_num):
    """生成单页图片（纯背景色模式）"""
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

def generate_image_with_bg(sentences, config, output_path, bg_path):
    """
    使用背景图片生成单页图片：
      - 加载背景图片并调整为页面尺寸
      - 在图片上绘制四句话，每张图片仅展示4句话，按照左右、左右排列（两行，每行两个）
      - 每句话绘制在带圆角半透明黑色背景的区域内，文字颜色为白色
    """
    page_width, page_height = config['page_size']
    try:
        bg_img = Image.open(bg_path).convert('RGB')
    except Exception as e:
        print(f"加载背景图片失败：{bg_path}, 错误：{e}")
        # 如果加载失败则使用背景色生成图片
        bg_img = Image.new('RGB', (page_width, page_height), config['bg_color'])
    
    # 裁剪背景图片以匹配页面尺寸比例，不拉伸
    orig_w, orig_h = bg_img.size
    target_ratio = page_width / page_height
    orig_ratio = orig_w / orig_h

    if orig_ratio > target_ratio:
        # 图片过宽，按高度裁剪宽度
        new_width = int(orig_h * target_ratio)
        offset = (orig_w - new_width) // 2
        crop_box = (offset, 0, offset + new_width, orig_h)
    else:
        # 图片过高，按宽度裁剪高度
        new_height = int(orig_w / target_ratio)
        offset = (orig_h - new_height) // 2
        crop_box = (0, offset, orig_w, offset + new_height)
    
    bg_img = bg_img.crop(crop_box)
    bg_img = bg_img.resize((page_width, page_height))
    
    draw = ImageDraw.Draw(bg_img, 'RGBA')
    
    try:
        font = ImageFont.truetype(config['font'], config['font_size'])
    except IOError:
        font = ImageFont.load_default()
    
    # 定义用于绘制文本框的边距和填充
    # 使用配置中 margins 的值：左上右下
    left_margin, top_margin, right_margin, bottom_margin = config['margins']
    padding = 20  # 文本框内边距
    radius = 50  # 圆角半径
    
    # 如果不足4句话，补足空字符串
    if len(sentences) < 4:
        sentences += [""] * (4 - len(sentences))
    
    # 如果一句话超过24个字，分割到下一句
    for i, sentence in enumerate(sentences):
        if len(sentence) > 24:
            sentences[i] = sentence[:24]
            sentences.insert(i+1, sentence[24:])
    
    for i, sentence in enumerate(sentences[:4]):
        if not sentence:
            continue
        bbox = font.getbbox(sentence)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        box_width = text_width + 4 * padding
        box_height = text_height + 2 * padding
        
        x = left_margin / 2

        y = top_margin + i * 300 + 100
        
        # 绘制圆角半透明黑色矩形背景
        rect_coords = [x, y, x + box_width, y + box_height]
        draw.rounded_rectangle(rect_coords, radius=radius, fill=(0, 0, 0, 180))
        # 绘制文本（白色文字）
        text_x = x + 2 * padding
        text_y = y + padding / 2
        draw.text((text_x, text_y), sentence, font=font, fill="#FFFFFF")
    
    bg_img.save(output_path)

def parse_color(color_str):
    """解析颜色字符串"""
    try:
        return ImageColor.getrgb(color_str)
    except ValueError:
        return ImageColor.getrgb('black')

def main():
    parser = argparse.ArgumentParser(description='Generate images from text with optional background images and watermark.')
    parser.add_argument('input', help='Input text file path')
    parser.add_argument('output_dir', help='Output directory')
    # 文字样式参数
    parser.add_argument('--font', default='./MSYH.TTC', help='Font file path')
    parser.add_argument('--font_size', type=int, default=42, help='Font size')
    parser.add_argument('--text_color', default='#eef1f3', help='Text color')
    parser.add_argument('--bg_color', default='#030607', help='Background color')
    parser.add_argument('--line_spacing', type=int, default=30, help='Line spacing')
    parser.add_argument('--char_spacing', type=int, default=2, help='Character spacing')
    parser.add_argument('--margins', type=int, nargs=4, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'), 
                        default=[100, 100, 100, 100], help='Page margins')
    parser.add_argument('--page_size', type=int, nargs=2, metavar=('WIDTH', 'HEIGHT'), 
                        default=[1200, 1600], help='Image dimensions')
    # 水印参数（原有，用于背景色模式）
    parser.add_argument('--watermark_text', help='Watermark text', default='')
    parser.add_argument('--watermark_font', help='Watermark font', default='./MSYH.TTC')
    parser.add_argument('--watermark_font_size', type=int, default=72, help='Watermark font size')
    parser.add_argument('--watermark_color', default='#30303060', help='Watermark color with alpha')
    parser.add_argument('--watermark_position', choices=['top_left', 'top_right', 'bottom_left', 'bottom_right', 'center'], 
                        default='center', help='Watermark position')
    parser.add_argument('--watermark_angle', type=int, default=45, help='Rotation angle')
    
    parser.add_argument('--bg_folder', help='Background images folder path', default='bg_images')
    parser.add_argument('--bg_limit', type=int, default=3, help='Number of background images to use')
    
    args = parser.parse_args()
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)

    # 清空输出目录
    for f in os.listdir(args.output_dir):
        os.remove(os.path.join(args.output_dir, f))
    
    # 读取文本
    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()
        # 违禁词过滤替换
        with open('filter.txt', 'r', encoding='utf-8') as filter_file:
            filter_list = filter_file.readlines()
            for filter_word in filter_list:
                filter_word = filter_word.split(',')
                word = filter_word[0]
                text = text.replace(word, filter_word[1].replace('\n', ''))
    
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
    
    # 若设置了背景图片，则优先使用背景图片生成图片
    if args.bg_folder and args.bg_limit > 0:
        # 获取背景图片列表（支持jpg, jpeg, png）
        bg_images = [os.path.join(args.bg_folder, f) for f in os.listdir(args.bg_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not bg_images:
            print("指定的背景图片文件夹中未找到有效图片，将使用背景色生成图片。")
        else:
            random.shuffle(bg_images)
            bg_images = bg_images[:args.bg_limit]
        
        # 将全文拆分为句子（支持中文标点和英文标点）
        sentence_list = re.split(r'(?<=[。！？.?!\n])+(?![。！？.?!」])', text)
        sentence_list = [s.strip() for s in sentence_list if s.strip()]
        
        num_bg_pages = len(bg_images)
        # 每页显示4句话
        chunks = []
        for i in range(num_bg_pages):
            chunk = sentence_list[i*4:(i+1)*4]
            # 如果不足4句，补空字符串
            while len(chunk) < 4:
                chunk.append("")
            chunks.append(chunk)
        
        for i, (bg, sentences) in enumerate(zip(bg_images, chunks)):
            output_path = os.path.join(args.output_dir, f'page_bg_{i+1:03d}.jpg')
            generate_image_with_bg(sentences, config, output_path, bg)
            print(f'Generated with background image: {output_path}')
        
        # 剩余的文本
        remaining_text = "\n".join(sentence_list[num_bg_pages*4:])
    else:
        remaining_text = text
    # 使用背景色生成模式（原有逻辑）处理剩余文本
    if remaining_text.strip():
        pages = split_into_pages(remaining_text, config)
        for i, page in enumerate(pages):
            output_path = os.path.join(args.output_dir, f'page_{i+1:03d}.jpg')
            generate_image(page, config, output_path, i+1)
            print(f'Generated with background color: {output_path}')

if __name__ == '__main__':
    main()