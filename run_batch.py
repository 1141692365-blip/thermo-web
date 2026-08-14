# run_batch.py - simple CLI runner to test processing without Streamlit
import argparse
from processor import process_batch_files

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_dir', required=True)
    parser.add_argument('--output_dir', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--cp_value', type=float)
    group.add_argument('--cp_file')
    parser.add_argument('--force_density', type=float, default=None)
    args = parser.parse_args()
    out_dir, summary = process_batch_files(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        cp_value=args.cp_value,
        cp_file=args.cp_file,
        force_density=args.force_density,
        generate_html=True
    )
    print("Processed. Outputs in:", out_dir)
    print(summary)

if __name__ == '__main__':
    main()
