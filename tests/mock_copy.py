import argparse
import shutil


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
shutil.copyfile(args.input, args.output)
