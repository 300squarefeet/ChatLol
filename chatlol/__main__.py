import socket
import sys

from chatlol import config


def main() -> None:
    import uvicorn

    # Optional port argument: `chatlol 9000`
    port = config.PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Penggunaan: chatlol [port]")
            sys.exit(1)

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        local_ip = "127.0.0.1"

    print(f"\n ChatLol berjalan di:")
    print(f"  Lokal        → http://localhost:{port}")
    print(f"  WiFi         → http://{local_ip}:{port}")
    print(f"  File Manager → http://{local_ip}:{port}/files\n")

    uvicorn.run("chatlol.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
