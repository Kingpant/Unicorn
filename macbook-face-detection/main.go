package main

import (
	"flag"
	"image"
	"image/color"
	"log"
	"strconv"

	"gocv.io/x/gocv"
)

func main() {
	cascade := flag.String("cascade",
		"/opt/homebrew/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
		"path to Haar cascade XML")
	device := flag.Int("device", 0, "camera device index (0 = built-in MacBook cam)")
	flag.Parse()

	webcam, err := gocv.OpenVideoCapture(*device)
	if err != nil {
		log.Fatalf("cannot open camera %d: %v", *device, err)
	}
	defer webcam.Close()

	window := gocv.NewWindow("Face Detection — press Q to quit")
	defer window.Close()

	classifier := gocv.NewCascadeClassifier()
	defer classifier.Close()
	if !classifier.Load(*cascade) {
		log.Fatalf("cannot load cascade: %s", *cascade)
	}

	img := gocv.NewMat()
	defer img.Close()

	gray := gocv.NewMat()
	defer gray.Close()

	green := color.RGBA{R: 0, G: 255, B: 0, A: 255}
	white := color.RGBA{R: 255, G: 255, B: 255, A: 255}

	log.Printf("camera %d opened — press Q or ESC to quit", *device)

	for {
		if ok := webcam.Read(&img); !ok || img.Empty() {
			continue
		}

		gocv.CvtColor(img, &gray, gocv.ColorBGRToGray)

		faces := classifier.DetectMultiScaleWithParams(
			gray, 1.1, 5, 0,
			image.Point{X: 80, Y: 80},
			image.Point{},
		)

		for _, r := range faces {
			gocv.Rectangle(&img, r, green, 2)
		}

		label := strconv.Itoa(len(faces)) + " face(s)"
		gocv.PutText(&img, label, image.Point{X: 10, Y: 30},
			gocv.FontHersheySimplex, 1.0, white, 2)

		window.IMShow(img)
		key := window.WaitKey(1)
		if key == 27 || key == 'q' || key == 'Q' {
			break
		}
	}
}
