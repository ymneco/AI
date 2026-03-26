"""Allow running the viewer server as: python -m spatial.viewer"""
from spatial.viewer.server import run_server

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Spatial Awareness 3D Viewer Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
