import base64
from collections import defaultdict
import math
import json
import os
import sys
import argparse
import hashlib
import imageio.v2 as imageio

# CONFIG CONSTS
COLUMN_COUNT = 70
ROW_COUNT = 45

RGB_HEX_CODES = [
            '#a9a9a9', '#7b68ee', '#2f4f4f', '#556b2f', '#8b4513', '#6b8e23', '#a52a2a',
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

MARKER_HEX_CODES = ['#ff0000', '#00ff00', '#0000ff']

# GENERAL CONSTS
WHITE = (255, 255, 255)
SAMPLING_MIN_THRESHOLD = 5
SAMPLING_SMALL_THRESHOLD = 15
SAMPLING_LARGE_SQUARES = 8
SAMPLING_SMALL_SQUARES = 4

class ColorDecoder:
    def __init__(self, video_path):
        self.video_path = video_path
        self.total_squares = ROW_COUNT * COLUMN_COUNT
        self.data_squares = self.total_squares - 2

        self.char_set = [
            'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
            '+', '/', '=',
        ]

        self.rgb_codes = []
        for hex_color in RGB_HEX_CODES:
            self.rgb_codes.append(self.hex_to_rgb(hex_color))

        self.marker_codes = []
        for hex_color in MARKER_HEX_CODES:
            self.marker_codes.append(self.hex_to_rgb(hex_color))

        self.color_to_char = {}
        for i, char in enumerate(self.char_set):
            self.color_to_char[self.rgb_codes[i]] = char

        self.char_color_stats = defaultdict(lambda: {'colors': [], 'mean': None})

    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def color_distance(self, c1, c2):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

    def convert_color_to_char(self, rgb, use_learned):
        min_distance = self.color_distance(rgb, WHITE)
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

    def convert_color_to_marker(self, rgb):
        min_distance = self.color_distance(rgb, WHITE)
        best_marker = None

        for i, color in enumerate(self.marker_codes):
            distance = self.color_distance(rgb, color)
            if distance < min_distance:
                min_distance = distance
                best_marker = i

        return best_marker

    def sample_cell(self, frame, row, col):
        height, width = frame.shape[:2]

        square_width = width / COLUMN_COUNT
        square_height = height / ROW_COUNT

        centre_x = (col * square_width) + (square_width / 2)
        centre_y = (row * square_height) + (square_height / 2)

        if square_width < SAMPLING_MIN_THRESHOLD:
            pixel = frame[int(centre_y), int(centre_x)]
            return (int(pixel[0]), int(pixel[1]), int(pixel[2]))

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
                pixel = frame[sample_y, sample_x]
                red_sum += int(pixel[0])
                green_sum += int(pixel[1])
                blue_sum += int(pixel[2])
                count += 1

        red_final = int(red_sum / count)
        green_final = int(green_sum / count)
        blue_final = int(blue_sum / count)

        return (red_final, green_final, blue_final)

    def extract_grid_from_frame(self, frame):
        colors = []
        for row in range(ROW_COUNT):
            for col in range(COLUMN_COUNT):
                colors.append(self.sample_cell(frame, row, col))

        return colors

    def read_markers(self, frame):
        first = self.convert_color_to_marker(self.sample_cell(frame, 0, 0))
        last = self.convert_color_to_marker(self.sample_cell(frame, ROW_COUNT - 1, COLUMN_COUNT - 1))
        return first, last

    def grid_to_string(self, grid_colors, use_learned=False):
        chars = []

        for color in grid_colors[1:-1]:
            char = self.convert_color_to_char(color, use_learned)
            if char is None:
                continue

            chars.append(char)

        built_string = ''.join(chars)

        return built_string

    def read_grids(self, debug=False):
        try:
            reader = imageio.get_reader(self.video_path, format='FFMPEG')
        except Exception as e:
            print("[-] Could not open recording: {}".format(str(e).splitlines()[0]))
            return []

        if debug:
            meta = reader.get_meta_data()
            print("[*] Video Info:")
            print("\t[*] Size: {}".format(meta.get('size')))
            print("\t[*] FPS: {}".format(meta.get('fps')))
            print("\t[*] Duration: {}s".format(meta.get('duration')))

        grids = []
        run = []
        run_marker = None
        expected_marker = 0
        run_lengths = []
        frame_count = 0
        skipped_start = 0
        skipped_mismatch = 0
        missed = 0
        found_end = False

        for frame in reader:
            frame_count += 1
            first, last = self.read_markers(frame)

            if first != last:
                skipped_mismatch += 1
                continue

            if first is None:
                if run_marker is None:
                    skipped_start += 1
                    continue
                print("[+] Detected end grid at frame {}".format(frame_count))
                found_end = True
                break

            if run_marker is None:
                print("[+] Detected first grid at frame {}".format(frame_count))

            if first != run_marker:
                if run:
                    grids.append(self.extract_grid_from_frame(run[len(run) // 2]))
                    run_lengths.append(len(run))

                if first != expected_marker:
                    print("[-] Missed a grid before frame {}".format(frame_count))
                    missed += 1

                expected_marker = (first + 1) % len(self.marker_codes)
                run_marker = first
                run = []

            run.append(frame)

        reader.close()

        if run:
            grids.append(self.extract_grid_from_frame(run[len(run) // 2]))
            run_lengths.append(len(run))

        if not grids:
            print("[-] No grids found in recording")
            print("\t[*] Check the recorded region only contains the grid")
            return []

        if not found_end:
            print("[-] No end grid found, the recording may have been stopped too early")

        print("[+] Found {} grids after skipping {} white frames".format(len(grids), skipped_start))

        if debug:
            print("[*] Skipped {} frames where the markers did not match".format(skipped_mismatch))
            print("[*] Frames per grid: min {}, max {}".format(min(run_lengths), max(run_lengths)))

        if missed:
            print("[-] Grids missed: {}, the output will be incomplete".format(missed))
            print("\t[*] Try increasing the delay in flash.html or recording at a higher FPS")

        return grids

    def train_from_known_base64(self, known_base64_file, output_mapping_file):

        with open(known_base64_file, 'r') as f:
            known_base64 = f.read().strip()

        print("[+] Extracting frames from video")

        grids = self.read_grids()
        if not grids:
            return False

        expected_grids = math.ceil(len(known_base64) / self.data_squares)

        if len(grids) == expected_grids:
            print("[+] Total grids matches expected of: {}".format(expected_grids))
        else:
            print("[-] Total grids does not match expected")
            print("\t[-] Expected grids: {}".format(expected_grids))
            print("\t[-] Found grids: {}".format(len(grids)))
            return False

        char_position = 0

        for grid in grids:
            for color in grid[1:-1]:
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

        missing = [char for char in self.char_set if char not in self.char_color_stats]
        if missing:
            print("[-] No colors learned for: {}".format(' '.join(missing)))

        return True

    def load_learned_mappings(self, mapping_file):
        with open(mapping_file, 'r') as f:
            data = json.load(f)

        mappings = data.get('mappings', data)

        for char, char_data in mappings.items():
            self.char_color_stats[char]['mean'] = tuple(char_data['mean'])
            self.char_color_stats[char]['count'] = char_data['count']

        print("[+] Loaded {} color to character mappings".format(len(self.char_color_stats)))

        if len(self.char_color_stats) < len(self.char_set):
            print("[-] Mappings are missing {} characters, consider re-training".format(len(self.char_set) - len(self.char_color_stats)))

        return True


    def decode_video(self, output_file, use_learned=False, debug=False):
        print("[+] Decoding video")

        grids = self.read_grids(debug)
        if not grids:
            return False

        base64_string = ""
        for i, grid in enumerate(grids):
            grid_string = self.grid_to_string(grid, use_learned=use_learned)
            base64_string += grid_string

            if (i + 1) % 100 == 0:
                print("[+] Processed {} of {} grids".format(i+1, len(grids)))

        if debug:
            print(f"[*] Base64 string length: {len(base64_string)}")
            with open('debug_base64.txt', 'w') as f:
                f.write(base64_string)
            print("[*] Saved base64 string to debug_base64.txt for debugging")

        try:
            missing_padding = len(base64_string) % 4
            if missing_padding:
                print("[-] Base64 length is not a multiple of 4, some cells may have been misread")
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

    if not os.path.isfile(args.recording):
        print("[!] Recording not found: {}".format(args.recording))
        sys.exit(1)

    if args.train:
        if not args.base64:
            print("[!] Must provide known base64 for training")
            print("\t[*] Use -b64 or --base64 with path to known base64 for the flashed file")
            sys.exit(1)

        if not os.path.isfile(args.base64):
            print("[!] Known base64 file not found: {}".format(args.base64))
            sys.exit(1)

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
            sys.exit(1)

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
            print("\t[*] Use -cm or --color-mappings to specify color mappings")
            print("\t[*] Or use -dm or --use-default-mappings to use default mappings")
            sys.exit(1)

        if args.use_default_mappings and args.color_mappings:
            print("[!] Cannot specify both using default mappings and color mappings")
            sys.exit(1)

        if args.color_mappings and not os.path.isfile(args.color_mappings):
            print("[!] Color mappings not found: {}".format(args.color_mappings))
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
            sys.exit(1)


if __name__ == "__main__":
    main()
