import asyncio
import os
import sys

# Add strategy root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.pipeline_service import _merge_insta_output

def run_merge():
    brand_slug = "google_0caccfe6"
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", brand_slug)
    print(f"Merging instagram files for {brand_slug} into {output_dir}...")
    _merge_insta_output(brand_slug, output_dir)
    print("Merge completed successfully!")

if __name__ == '__main__':
    run_merge()
