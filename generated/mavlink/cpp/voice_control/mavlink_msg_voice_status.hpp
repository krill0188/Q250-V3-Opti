// MESSAGE VOICE_STATUS support class

#pragma once

namespace mavlink {
namespace voice_control {
namespace msg {

/**
 * @brief VOICE_STATUS message
 *
 * Voice system status from drone to GCS
 */
struct VOICE_STATUS : mavlink::Message {
    static constexpr msgid_t MSG_ID = 30001;
    static constexpr size_t LENGTH = 58;
    static constexpr size_t MIN_LENGTH = 58;
    static constexpr uint8_t CRC_EXTRA = 204;
    static constexpr auto NAME = "VOICE_STATUS";


    uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot */
    uint8_t vad_active; /*<  VAD active (1) or inactive (0) */
    uint8_t asr_active; /*<  ASR active (1) or inactive (0) */
    std::array<char, 32> current_model; /*<  Current ASR model name */
    float cpu_usage; /*<  CPU usage percentage */
    float memory_usage_mb; /*<  Memory usage in MB */
    uint32_t commands_processed; /*<  Total commands processed */
    uint32_t commands_failed; /*<  Failed commands count */
    float last_latency_ms; /*<  Last command processing latency */


    inline std::string get_name(void) const override
    {
            return NAME;
    }

    inline Info get_message_info(void) const override
    {
            return { MSG_ID, LENGTH, MIN_LENGTH, CRC_EXTRA };
    }

    inline std::string to_yaml(void) const override
    {
        std::stringstream ss;

        ss << NAME << ":" << std::endl;
        ss << "  timestamp_ms: " << timestamp_ms << std::endl;
        ss << "  vad_active: " << +vad_active << std::endl;
        ss << "  asr_active: " << +asr_active << std::endl;
        ss << "  current_model: \"" << to_string(current_model) << "\"" << std::endl;
        ss << "  cpu_usage: " << cpu_usage << std::endl;
        ss << "  memory_usage_mb: " << memory_usage_mb << std::endl;
        ss << "  commands_processed: " << commands_processed << std::endl;
        ss << "  commands_failed: " << commands_failed << std::endl;
        ss << "  last_latency_ms: " << last_latency_ms << std::endl;

        return ss.str();
    }

    inline void serialize(mavlink::MsgMap &map) const override
    {
        map.reset(MSG_ID, LENGTH);

        map << timestamp_ms;                  // offset: 0
        map << cpu_usage;                     // offset: 4
        map << memory_usage_mb;               // offset: 8
        map << commands_processed;            // offset: 12
        map << commands_failed;               // offset: 16
        map << last_latency_ms;               // offset: 20
        map << vad_active;                    // offset: 24
        map << asr_active;                    // offset: 25
        map << current_model;                 // offset: 26
    }

    inline void deserialize(mavlink::MsgMap &map) override
    {
        map >> timestamp_ms;                  // offset: 0
        map >> cpu_usage;                     // offset: 4
        map >> memory_usage_mb;               // offset: 8
        map >> commands_processed;            // offset: 12
        map >> commands_failed;               // offset: 16
        map >> last_latency_ms;               // offset: 20
        map >> vad_active;                    // offset: 24
        map >> asr_active;                    // offset: 25
        map >> current_model;                 // offset: 26
    }
};

} // namespace msg
} // namespace voice_control
} // namespace mavlink
