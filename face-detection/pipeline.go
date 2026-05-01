package main

import (
	"bytes"
	"fmt"
	"image"
	"image/color"
	"log"
	"mime"
	"mime/multipart"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"gocv.io/x/gocv"
)

type pipeline struct {
	camURL      string
	cascadePath string
	bcast       broadcaster
	faceCount   atomic.Int64
}

func newPipeline(camURL, cascadePath string) *pipeline {
	p := &pipeline{
		camURL:      camURL,
		cascadePath: cascadePath,
	}
	p.bcast.clients = make(map[chan []byte]struct{})
	return p
}

// run starts the read → detect → broadcast loop. Call in a goroutine.
func (p *pipeline) run() {
	frames := make(chan []byte, 2)
	go p.readLoop(frames)
	p.detectLoop(frames)
}

// readLoop reconnects to the ESP32 MJPEG stream whenever it drops.
func (p *pipeline) readLoop(out chan<- []byte) {
	for {
		if err := p.readStream(out); err != nil {
			log.Printf("stream error: %v — retrying in 2s", err)
		}
		time.Sleep(2 * time.Second)
	}
}

func (p *pipeline) readStream(out chan<- []byte) error {
	resp, err := http.Get(p.camURL)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	_, params, err := mime.ParseMediaType(resp.Header.Get("Content-Type"))
	if err != nil {
		return fmt.Errorf("parse Content-Type: %w", err)
	}
	boundary, ok := params["boundary"]
	if !ok {
		return fmt.Errorf("no boundary in Content-Type")
	}

	mr := multipart.NewReader(resp.Body, boundary)
	for {
		part, err := mr.NextPart()
		if err != nil {
			return err
		}
		buf := new(bytes.Buffer)
		if _, err := buf.ReadFrom(part); err != nil {
			return err
		}
		select {
		case out <- buf.Bytes():
		default: // drop frame if detector is busy
		}
	}
}

func (p *pipeline) detectLoop(frames <-chan []byte) {
	classifier := gocv.NewCascadeClassifier()
	defer classifier.Close()
	if !classifier.Load(p.cascadePath) {
		log.Fatalf("cannot load cascade: %s", p.cascadePath)
	}

	for jpegData := range frames {
		img, err := gocv.IMDecode(jpegData, gocv.IMReadColor)
		if err != nil || img.Empty() {
			img.Close()
			continue
		}

		gray := gocv.NewMat()
		gocv.CvtColor(img, &gray, gocv.ColorBGRToGray)

		rects := classifier.DetectMultiScaleWithParams(
			gray, 1.1, 5, 0,
			image.Point{X: 50, Y: 50},
			image.Point{},
		)
		gray.Close()

		for _, r := range rects {
			gocv.Rectangle(&img, r, color.RGBA{R: 0, G: 255, B: 0, A: 255}, 2)
		}
		p.faceCount.Store(int64(len(rects)))

		native, err := gocv.IMEncode(".jpg", img)
		img.Close()
		if err != nil {
			continue
		}
		raw := native.GetBytes()
		frame := make([]byte, len(raw))
		copy(frame, raw)
		native.Close()

		p.bcast.broadcast(frame)
	}
}

// broadcaster fans annotated JPEG frames out to all connected HTTP stream clients.
type broadcaster struct {
	mu      sync.Mutex
	clients map[chan []byte]struct{}
}

func (b *broadcaster) subscribe() chan []byte {
	ch := make(chan []byte, 1)
	b.mu.Lock()
	b.clients[ch] = struct{}{}
	b.mu.Unlock()
	return ch
}

func (b *broadcaster) unsubscribe(ch chan []byte) {
	b.mu.Lock()
	delete(b.clients, ch)
	b.mu.Unlock()
}

func (b *broadcaster) broadcast(frame []byte) {
	b.mu.Lock()
	for ch := range b.clients {
		select {
		case ch <- frame:
		default: // slow client — skip frame
		}
	}
	b.mu.Unlock()
}
