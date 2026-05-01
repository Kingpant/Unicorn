#include <string.h>
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_camera.h"
#include "img_converters.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "http_server.h"

#define PART_BOUNDARY "123456789000000000000987654321"
#define STREAM_CONTENT_TYPE "multipart/x-mixed-replace;boundary=" PART_BOUNDARY
#define STREAM_BOUNDARY     "\r\n--" PART_BOUNDARY "\r\n"
#define STREAM_PART         "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n"

#define SW_JPEG_QUALITY 20   // quality for frame2jpg() software conversion (lower = faster + smaller)
#define STREAM_FRAME_MS 120  // ~8 fps cap — gives WiFi send buffer time to drain

static const char *TAG = "http_server";

// Converts frame to JPEG if sensor does not produce hardware JPEG (e.g. GC2145).
// Returns true and sets *out_buf / *out_len. Caller must free(*out_buf) if *did_convert.
static bool get_jpeg(camera_fb_t *fb, uint8_t **out_buf, size_t *out_len, bool *did_convert)
{
    if (fb->format == PIXFORMAT_JPEG) {
        *out_buf     = fb->buf;
        *out_len     = fb->len;
        *did_convert = false;
        return true;
    }
    *did_convert = frame2jpg(fb, SW_JPEG_QUALITY, out_buf, out_len);
    return *did_convert;
}

// GET /capture — single JPEG snapshot.
// Poll from Python/OpenCV: requests.get("http://<ip>/capture").content
static esp_err_t capture_handler(httpd_req_t *req)
{
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        ESP_LOGE(TAG, "capture failed");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    uint8_t *jpg_buf = NULL;
    size_t   jpg_len = 0;
    bool     converted = false;

    if (!get_jpeg(fb, &jpg_buf, &jpg_len, &converted)) {
        ESP_LOGE(TAG, "JPEG conversion failed");
        esp_camera_fb_return(fb);
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    esp_err_t res = httpd_resp_send(req, (const char *)jpg_buf, jpg_len);

    if (converted) free(jpg_buf);
    esp_camera_fb_return(fb);
    return res;
}

// GET /stream — continuous MJPEG stream.
// Open in browser or: cv2.VideoCapture("http://<ip>/stream")
static esp_err_t stream_handler(httpd_req_t *req)
{
    char part_buf[64];

    httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE(TAG, "frame capture failed");
            break;
        }

        uint8_t *jpg_buf = NULL;
        size_t   jpg_len = 0;
        bool     converted = false;

        if (!get_jpeg(fb, &jpg_buf, &jpg_len, &converted)) {
            ESP_LOGE(TAG, "JPEG conversion failed");
            esp_camera_fb_return(fb);
            break;
        }

        esp_err_t res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));

        if (res == ESP_OK) {
            size_t hlen = snprintf(part_buf, sizeof(part_buf), STREAM_PART, jpg_len);
            res = httpd_resp_send_chunk(req, part_buf, hlen);
        }
        if (res == ESP_OK) {
            res = httpd_resp_send_chunk(req, (const char *)jpg_buf, jpg_len);
        }

        if (converted) free(jpg_buf);
        esp_camera_fb_return(fb);

        if (res != ESP_OK) break;  // client disconnected

        vTaskDelay(pdMS_TO_TICKS(STREAM_FRAME_MS));  // pace frames to avoid EAGAIN
    }

    return ESP_OK;
}

esp_err_t http_server_start(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port      = 80;
    config.stack_size       = 8192;
    config.send_wait_timeout = 10;  // seconds before giving up on a slow client

    httpd_handle_t server = NULL;
    ESP_ERROR_CHECK(httpd_start(&server, &config));

    httpd_uri_t capture_uri = {
        .uri     = "/capture",
        .method  = HTTP_GET,
        .handler = capture_handler,
    };
    httpd_register_uri_handler(server, &capture_uri);

    httpd_uri_t stream_uri = {
        .uri     = "/stream",
        .method  = HTTP_GET,
        .handler = stream_handler,
    };
    httpd_register_uri_handler(server, &stream_uri);

    ESP_LOGI(TAG, "HTTP server started on :80");
    ESP_LOGI(TAG, "  /capture  — single JPEG");
    ESP_LOGI(TAG, "  /stream   — MJPEG stream");
    return ESP_OK;
}
