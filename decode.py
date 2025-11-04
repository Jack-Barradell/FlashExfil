import cv2
import base64
from collections import defaultdict
import math
import json
import sys 
import argparse
import hashlib
import math

# CONFIG CONSTS
COLUMN_COUNT = 70
ROW_COUNT = 45
CELL_SIZE = 14
END_WHITE_PERCENTAGE = 0.99

RGB_HEX_CODES = [
            '#a9a9a9', '#7b68ee', "#adb3b0", '#556b2f', '#8b4513', '#6b8e23', '#a52a2a',
            '#228b22', '#191970', '#708090', '#483d8b', '#5f9ea0', '#3cb371', '#bc8f8f',
            '#663399', '#b8860b', '#bdb76b', '#cd853f', '#4682b4', '#000080', '#d2691e',
            '#9acd32', '#20b2aa', '#cd5c5c', '#32cd32', '#8fbc8f', '#8b008b', '#b03060',
            '#d2b48c', '#66cdaa', '#9932cc', '#ff4500', '#ff8c00', '#ffd700', '#c71585',
            '#0000cd', '#00ff00', '#ba55d3', '#00fa9a', '#4169e1', '#dc143c', '#00ffff',
            '#00bfff', '#9370db', '#0000ff', '#a020f0', '#adff2f', '#ff6347', '#d8bfd8',
            '#ff00ff', '#1e90ff', '#db7093', '#f0e68c', '#ffff54', '#dda0dd', '#87ceeb',
            '#ff1493', '#ffa07a', '#afeeee', '#ee82ee', '#98fb98', '#7fffd4', '#ff69b4',
            '#8b4789', '#ffb6c1'
        ]

# GENERAL CONSTS
WHITE = (255, 255, 255)
GENERAL_WHITE_THRESHOLD = 3
GRID_WHITE_THRESHOLD = 40
SAMPLING_MIN_THRESHOLD = 5
SAMPLING_SMALL_THRESHOLD = 15
SAMPLING_LARGE_SQUARES = 8
SAMPLING_SMALL_SQUARES = 4

class ColorDecoder:
    def __init__(self, video_path):
        self.video_path = video_path
        self.total_squares = ROW_COUNT * COLUMN_COUNT
        
        self.char_set = [
            'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
            '+', '/', '=',
        ]
        
        self.rgb_codes = []
        for hex_color in RGB_HEX_CODES:
            hex_color = hex_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            self.rgb_codes.append(rgb)
        
        self.color_to_char = {}
        for i, char in enumerate(self.char_set):
            self.color_to_char[self.rgb_codes[i]] = char
        
        self.char_color_stats = defaultdict(lambda: {'colors': [], 'mean': None})
    
    def color_distance(self, c1, c2):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
    
    def is_white(self, rgb):
        return self.color_distance(rgb, WHITE) < GENERAL_WHITE_THRESHOLD
    
    def is_white_grid(self, grid_colors):
        white_count = 0
        for color in grid_colors:
            distance = self.color_distance(color, WHITE)
            if distance < GRID_WHITE_THRESHOLD:
                white_count += 1
        
        white_percentage = white_count / len(grid_colors)
        return white_percentage >= END_WHITE_PERCENTAGE
    
    def convert_color_to_char(self, rgb, use_learned):
        min_distance = float("inf")
        best_char = None

        if use_learned:
            for char, stats in self.char_color_stats.items():
                distance = self.color_distance(rgb, stats["mean"])
                if distance < min_distance:
                    min_distance = distance
                    best_char = char
        else:
            for color in self.rgb_codes:
                distance = self.color_distance(rgb, color)
                if distance < min_distance:
                    min_distance = distance 
                    best_char = self.color_to_char[color]

        return best_char
    
    def extract_grid_from_frame(self, frame):
        height, width = frame.shape[:2]
        
        square_width = width / COLUMN_COUNT
        square_height = height / ROW_COUNT
        
        colors = []
        for row in range(ROW_COUNT):
            for col in range(COLUMN_COUNT):
                centre_x = (col * square_width) + (square_width / 2)
                centre_y = (row * square_height) + (square_height / 2)

                if square_width >= SAMPLING_MIN_THRESHOLD:
                    if square_width < SAMPLING_SMALL_THRESHOLD:
                        offset = min(square_width, square_height) / SAMPLING_LARGE_SQUARES
                    else:
                        offset = min(square_width, square_height) / SAMPLING_SMALL_SQUARES
                    
                    sample_points = [
                        (centre_x, centre_y),
                        (centre_x - offset, centre_y),
                        (centre_x + offset, centre_y),
                        (centre_x, centre_y - offset),
                        (centre_x, centre_y + offset),
                    ]
                    
                    red_sum = 0
                    green_sum = 0 
                    blue_sum = 0
                    count = 0
                    
                    for sample_x, sample_y in sample_points:
                        sample_x = int(sample_x)
                        sample_y = int(sample_y)
                        if sample_x < width and sample_y < height:
                            blue_green_red = frame[sample_y, sample_x]
                            red_sum += int(blue_green_red[2])
                            green_sum += int(blue_green_red[1])
                            blue_sum += int(blue_green_red[0])
                            count += 1
                    
                    red_final = int(red_sum / count)
                    green_final = int(green_sum / count)
                    blue_final = int(blue_sum / count)

                    rgb = (red_final, green_final, blue_final) 
                else:
                    blue_green_red = frame[int(centre_y), int(centre_x)]
                    rgb = (int(blue_green_red[2]), int(blue_green_red[1]), int(blue_green_red[0]))
                
                colors.append(rgb)

        return colors
    
    def grid_to_string(self, grid_colors, use_learned=False):
        chars = []

        for color in grid_colors:
            if self.is_white(color):
                continue
            
            if use_learned:
                char = self.convert_color_to_char(color, True)
            else:
                char = self.convert_color_to_char(color, False)
            
            chars.append(char)

        built_string = ''.join(chars)

        return built_string
    
    def grids_are_same(self, grid_one, grid_two, threshold=20):
        if grid_one is None or grid_two is None:
            return False
        
        differences = sum(self.color_distance(c1, c2) for c1, c2 in zip(grid_one, grid_two))
        mean_difference = differences / len(grid_one)
        
        if mean_difference <= threshold:
            return True
        else:
            return False
    
    def train_from_known_base64(self, known_base64_file, output_mapping_file):

        with open(known_base64_file, 'r') as f:
            known_base64 = f.read().strip()
        
        cap = cv2.VideoCapture(self.video_path)
        
        print("[+] Extracting frames from video")
        
        all_grids = []
        frame_count = 0
        skipped_start = 0
        encoding_started = False
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            grid_colors = self.extract_grid_from_frame(frame)
            
            if self.is_white_grid(grid_colors):
                if not encoding_started:
                    skipped_start += 1
                    continue
                else:
                    print("[+] Detected end grid at frame {}".format(frame_count))
                    break
            else:
                if not encoding_started:
                    print("[+] Detected first grid at frame {}".format(frame_count))
                    encoding_started = True
                all_grids.append(grid_colors)
        
        cap.release()

        print("[+] Extracted {} grids after skipping {} white frames".format(len(all_grids), skipped_start))
        
        unique_grids = []
        for grid in all_grids:
            if not unique_grids or not self.grids_are_same(grid, unique_grids[-1]):
                unique_grids.append(grid)
        
        expected_grids = math.ceil(len(known_base64) / self.total_squares)

        if len(unique_grids) == expected_grids:
            print("[+] Total unique grids matches expected of: {}".format(expected_grids))
        else:
            print("[-] Total unique grids does not match expected")
            print("\t[-] Expected grids: {}".format(expected_grids))
            print("\t[-] Unique grids: {}".format(len(unique_grids)))
    
        char_position = 0
        skipped_whites = 0
        
        for grid in unique_grids:
            for color in grid:
                if self.is_white(color):
                    skipped_whites += 1
                    continue
                
                if char_position >= len(known_base64):
                    break
                
                expected_char = known_base64[char_position]
                self.char_color_stats[expected_char]['colors'].append(color)
                char_position += 1
        
        if char_position != len(known_base64):
            print("[-] Character count does not match known base64")
            print("\t[-] Expected: {}".format(len(known_base64)))
            print("\t[-] Actual: {}".format(char_position))

        else:
            print("[+] Length of trained data matches known base64")
        
        for _, stats in self.char_color_stats.items():
            if stats['colors']:
                colors = stats['colors']
                mean_r = sum(c[0] for c in colors) / len(colors)
                mean_g = sum(c[1] for c in colors) / len(colors)
                mean_b = sum(c[2] for c in colors) / len(colors)
                stats['mean'] = (int(mean_r), int(mean_g), int(mean_b))
                stats['count'] = len(colors)

        mappings_to_save = {
            'mappings': {
                char: {
                    'mean': stats['mean'],
                    'count': stats['count'],
                }
                for char, stats in self.char_color_stats.items()
                if stats['mean'] is not None
            }
        }
        
        with open(output_mapping_file, 'w') as f:
            json.dump(mappings_to_save, f, indent=2)
        
        print("[+] Learned colors for {} characters".format(len(self.char_color_stats)))
        
        return True
    
    def load_learned_mappings(self, mapping_file):
        with open(mapping_file, 'r') as f:
            data = json.load(f)
        
        mappings = data.get('mappings', data)
        
        for char, char_data in mappings.items():
            self.char_color_stats[char]['mean'] = tuple(char_data['mean'])
            self.char_color_stats[char]['count'] = char_data['count']
        
        print("[+] Loaded {} color to character mappings".format(len(self.char_color_stats)))
        return True

    
    def decode_video(self, output_file, use_learned=False, debug=False):
        cap = cv2.VideoCapture(self.video_path)
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if debug:
            print("[*] Video Info:")
            print("\t[*] Total Frames: {}".format(total_frames))
            print("\t[*] FPS: {}".format(fps))

        print("[+] Decoding video")
        
        all_grids = []
        frame_count = 0
        skipped_start = 0
        encoding_started = False
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            grid_colors = self.extract_grid_from_frame(frame)
            
            if self.is_white_grid(grid_colors):
                if not encoding_started:
                    skipped_start += 1
                    continue
                else:
                    print("[+] Detected end grid at frame {}".format(frame_count))
                    break
            else:
                if not encoding_started:
                    print("[+] Detected first grid at frame {}".format(frame_count))
                    encoding_started = True
                all_grids.append((frame_count, grid_colors))
        
        cap.release()
        
        unique_grids = []
        for i, (frame_num, grid) in enumerate(all_grids):
            if i == 0 or not self.grids_are_same(grid, unique_grids[-1][1]):
                unique_grids.append((frame_num, grid))
        
        
        print("[+] Found {} unique grids".format(len(unique_grids)))
        
        base64_string = ""
        for i, (frame_num, grid) in enumerate(unique_grids):
            grid_string = self.grid_to_string(grid, use_learned=use_learned)
            base64_string += grid_string
            
            if (i + 1) % 100 == 0:
                print("[+] Processed {} of {} grids".format(i+1, len(unique_grids)))

        if debug:
            print(f"[*] Base64 string length: {len(base64_string)}")
            with open('debug_base64.txt', 'w') as f:
                f.write(base64_string)
            print("[*] Saved base64 string to debug_base64.txt for debugging")
        
        try:
            missing_padding = len(base64_string) % 4
            if missing_padding:
                base64_string += '=' * (4 - missing_padding)
            
            binary_data = base64.b64decode(base64_string)
            
            with open(output_file, 'wb') as f:
                f.write(binary_data)
            
            print("[+] Total file size: {} bytes".format(len(binary_data)))
            print("[+] SHA256 hash of decoded file: {}".format(hashlib.sha256(binary_data).hexdigest()))
            
            return True
            
        except Exception as e:
            print(f"[-] Error decoding base64: {e}")
            return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--recording", help="Path to recording of flashes", required=True)
    parser.add_argument("-t", "--train", help="Training mode", action="store_true")
    parser.add_argument("-b64", "--base64", help="Path to known base64 for training")
    parser.add_argument("-cm", "--color-mappings", help="Path to save or load color mappings, default=color_mapping.json")
    parser.add_argument("-dm", "--use-default-mappings", help="Use default color mappings instead of trained file (decode mode only)", action="store_true")
    parser.add_argument("-o", "--output", help="Path to save output file")
    parser.add_argument("-d", "--debug", help="Print debug messages", action="store_true")

    args = parser.parse_args()

    if args.train:
        if not args.base64:
            print("[!] Must provide known base64 for training")
            print("\t[*] Use -b64 or --base64 with path to known base64 for the flashed file")
            sys.exit(1)
        
        mappings_file = None 
        if args.use_default_mappings:
            print("[!] Cannot use default mappings during training")
            sys.exit(1)
        
        if args.output:
            print("[!] Output option is invalid for training")
            print("\t[*] Use -cm or --color-mappings to provide output location for training")

        if args.color_mappings:
            save_location = args.color_mappings
        else:
            save_location = "color_mapping.json"

        decoder = ColorDecoder(args.recording)

        trained = decoder.train_from_known_base64(args.base64, save_location)

        if trained:
            print("[+] Training complete")
        else:
            print("[-] Training failed")

    else:
        if args.base64:
            print("[!] Cannot use known base64 while decoding")
            sys.exit(1)

        if not args.output:
            print("[!] Must provide output location for decoded file")
            print("\t[*] Use -o or --output with path to save file")
            sys.exit(1)

        if not args.use_default_mappings and not args.color_mappings:
            print("[!] Must either provide color mappings or use default mappings")
            print("\t[*] User -cm or --color-mappings to specify color mappings")
            print("\t[*] Or use -dm or --use-default-mappings to use default mappings")
            sys.exit(1)

        if args.use_default_mappings and args.color_mappings:
            print("[!] Cannot specify both using default mappings and color mappings")
            sys.exit(1)

        decoder = ColorDecoder(args.recording)

        if args.use_default_mappings:
            custom_map = False
        else: 
            custom_map = True
            decoder.load_learned_mappings(args.color_mappings)

        decoded = decoder.decode_video(args.output, custom_map, args.debug)

        if decoded:
            print('[+] Decoded file to {}'.format(args.output))
        else:
            print("[-] Failed to decode file")
    

if __name__ == "__main__":
    main()