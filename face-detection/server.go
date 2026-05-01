package main

import (
	"fmt"
	"net/http"
)

const mjpegBoundary = "mjpegframe"

func (p *pipeline) streamHandler(w http.ResponseWriter, r *http.Request) {
	ch := p.bcast.subscribe()
	defer p.bcast.unsubscribe(ch)

	w.Header().Set("Content-Type", "multipart/x-mixed-replace;boundary="+mjpegBoundary)
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}

	for {
		select {
		case frame := <-ch:
			fmt.Fprintf(w, "--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n",
				mjpegBoundary, len(frame))
			if _, err := w.Write(frame); err != nil {
				return
			}
			fmt.Fprintf(w, "\r\n")
			flusher.Flush()
		case <-r.Context().Done():
			return
		}
	}
}

func (p *pipeline) healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"faces":%d}`, p.faceCount.Load())
}

func indexHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, indexHTML)
}

const indexHTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>ESP32-CAM Face Detection</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #111; color: #eee;
      font-family: system-ui, sans-serif;
      display: flex; flex-direction: column; align-items: center;
      padding: 2rem; gap: 1rem; min-height: 100vh;
    }
    h1 { font-size: 1.4rem; font-weight: 600; letter-spacing: .03em; }
    #stream {
      border: 2px solid #333; border-radius: 10px;
      max-width: 100%; background: #222;
    }
    #badge {
      font-size: 1.1rem; padding: .4rem 1rem;
      background: #1a1a1a; border: 1px solid #333; border-radius: 6px;
    }
    #badge span { color: #4ade80; font-weight: 700; }
  </style>
</head>
<body>
  <h1>ESP32-CAM — Face Detection</h1>
  <img id="stream" src="/stream" alt="annotated stream" />
  <div id="badge">Faces detected: <span id="count">—</span></div>
  <script>
    setInterval(async () => {
      try {
        const d = await (await fetch('/health')).json();
        document.getElementById('count').textContent = d.faces;
      } catch {}
    }, 500);
  </script>
</body>
</html>`
