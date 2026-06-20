import time
from fast_connect import FastConnectServer

if __name__ == "__main__":
    # Host 0.0.0.0 tells the cloud container to accept traffic externally
    # Render assigns an environment variable for the port automatically
    import os
    port = int(os.environ.get("PORT", 9999))
    
    print(f"Starting FastConnect Cloud Server on port {port}...")
    server = FastConnectServer(host='0.0.0.0', port=port)
    
    if server.start():
        print("Server is successfully running online.")
        # Keep the main thread alive indefinitely
        while True:
            time.sleep(3600)