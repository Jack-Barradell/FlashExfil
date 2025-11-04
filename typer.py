import sys
import pyautogui
import argparse
import time 

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Input file to type", required=True)
    parser.add_argument("-c", "--chunk", help="Chunk typing file content, for use if typing large files", action="store_true")
    parser.add_argument("-cs", "--chunk-size", help="Number of characters per chunk for use with --chunk (Default = 100, Minimum = 1)")
    parser.add_argument("-d", "--delay", help="Delay before typing starts in seconds (Default = 5, Minimum = 1)")
    parser.add_argument("-i", "--interval", help="Interval between key presses (Default = 0, Minimum = 0)")

    args = parser.parse_args()

    if args.delay and int(args.delay) >= 1:
        wait_time = int(args.delay)
    else:
        wait_time = 5

    if args.interval and float(args.interval) >= 0:
        interval = float(args.interval)
    else:
        interval = 0

    if args.chunk_size:
        if args.chunk and int(args.chunk_size) >= 1:
            chunk_size = int(args.chunk_size)
        else:
            print("[!] Must specify -c or --chunk to use chunk size")
            sys.exit(1)
    else:
        chunk_size = 100
    
    print("[+] Typing starts in {} seconds".format(wait_time))
    print("[*] Make sure your target window has focus")

    slept = 0
    while slept < wait_time:
        time.sleep(1)
        slept += 1

    print("[+] Typing starting")
    with open(args.file, "r") as f:
        if args.chunk:
            done = False
            while not done:
                read = 0
                chunk_list = []
                while read < chunk_size:
                    c = f.read(1)
                    if not c:
                        done = True
                        break 
                    chunk_list.append(c)
                    read += 1
                chunk_string = ''.join(chunk_list)
                pyautogui.write(chunk_string, interval)
        else:
            pyautogui.write(f.read(), interval)
    pyautogui.press('delete')
    print("[+] Typing complete")

if __name__ == '__main__':
    main()