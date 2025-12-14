"""Entry point for Fish Scale Measurement UI."""

import argparse
import webbrowser
import threading
import time
from pathlib import Path


def main():
    """Run the Fish Scale UI application."""
    parser = argparse.ArgumentParser(
        description='Fish Scale Measurement UI',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-d', '--image-dir',
        type=str,
        default='test_images',
        help='Directory to browse for images'
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=5010,
        help='Port to run the server on'
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not automatically open browser'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )

    args = parser.parse_args()

    # Resolve image directory to absolute path
    image_dir = Path(args.image_dir).resolve()
    if not image_dir.exists():
        print(f"Warning: Image directory '{image_dir}' does not exist. Creating it.")
        image_dir.mkdir(parents=True, exist_ok=True)

    from fish_scale_ui.app import create_app

    app = create_app(config={
        'IMAGE_DIR': image_dir,
    })

    # Open browser after short delay
    if not args.no_browser:
        def open_browser():
            time.sleep(1)
            webbrowser.open(f'http://127.0.0.1:{args.port}')

        threading.Thread(target=open_browser, daemon=True).start()

    print("Starting Fish Scale Measurement UI...")
    print(f"Image directory: {image_dir}")
    print(f"Opening browser at http://127.0.0.1:{args.port}")
    print("Press Ctrl+C to stop the server.")

    app.run(host='127.0.0.1', port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
