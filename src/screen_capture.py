import os
import mss
import mss.tools
from PIL import Image

def capture_screen(output_path: str = "data/screenshots/live_draft.png", monitor_index: int = 0) -> str:
    """
    Captures screen using mss and saves as PNG.
    monitor_index=0 captures all combined monitors.
    monitor_index=1 captures primary monitor.
    monitor_index=2 captures secondary monitor.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with mss.mss() as sct:
        monitors = sct.monitors
        if monitor_index < 0 or monitor_index >= len(monitors):
            monitor_index = 0
            
        selected_monitor = monitors[monitor_index]
        sct_img = sct.grab(selected_monitor)
        
        # Save image
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=output_path)
        
    return os.path.abspath(output_path)

if __name__ == "__main__":
    path = capture_screen()
    print(f"Captured screen successfully to: {path}")
