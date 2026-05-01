#include "esp_log.h"
#include "nvs_flash.h"
#include "wifi.h"
#include "camera.h"
#include "http_server.h"

static const char *TAG = "main";

void app_main(void)
{
    // NVS is required by the WiFi driver
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Camera must init before WiFi — both share the PLL on ESP32
    ESP_ERROR_CHECK(camera_init());
    ESP_ERROR_CHECK(wifi_init_sta());
    ESP_ERROR_CHECK(http_server_start());

    ESP_LOGI(TAG, "ready");
    ESP_LOGI(TAG, "  single frame : http://<ip>/capture");
    ESP_LOGI(TAG, "  live stream  : http://<ip>/stream");
}
