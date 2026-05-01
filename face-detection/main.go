package main

import (
	"flag"
	"log"
	"net/http"
)

func main() {
	camURL  := flag.String("cam", "", "ESP32-CAM MJPEG stream URL (e.g. http://192.168.1.x/stream)")
	addr    := flag.String("addr", ":8080", "HTTP listen address")
	cascade := flag.String("cascade",
		"/opt/homebrew/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
		"path to Haar cascade XML (ships with OpenCV)")
	flag.Parse()

	if *camURL == "" {
		log.Fatal("--cam is required, e.g. --cam http://192.168.1.x/stream")
	}

	p := newPipeline(*camURL, *cascade)
	go p.run()

	http.HandleFunc("/", indexHandler)
	http.HandleFunc("/stream", p.streamHandler)
	http.HandleFunc("/health", p.healthHandler)

	log.Printf("face-detection server listening on http://localhost%s", *addr)
	log.Fatal(http.ListenAndServe(*addr, nil))
}
