// MESSAGE VOICE_COMMAND support class

#pragma once

namespace mavlink {
namespace voice_control {
namespace msg {

/**
 * @brief VOICE_COMMAND message
 *
 * Voice command from GCS to drone
 */
struct VOICE_COMMAND : mavlink::Message {
    static constexpr msgid_t MSG_ID = 30000;
    static constexpr size_t LENGTH = 211;
    static constexpr size_t MIN_LENGTH = 211;
    static constexpr uint8_t CRC_EXTRA = 147;
    static constexpr auto NAME = "VOICE_COMMAND";


    uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot */
    std::array<char, 128> command_text; /*<  Raw recognized text */
    std::array<char, 32> parsed_action; /*<  Parsed action: TAKEOFF, LAND, GOTO, RTL, HOVER, SET_MODE, ARM, DISARM */
    std::array<float, 10> params; /*<  Action parameters (lat, lon, alt, speed, heading, etc.) */
    uint8_t param_count; /*<  Number of valid parameters */
    float confidence; /*<  ASR confidence 0.0-1.0 */
    uint8_t is_final; /*<  Final result (1) or partial (0) */
    uint8_t command_id; /*<  Unique command sequence ID */


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
        ss << "  command_text: \"" << to_string(command_text) << "\"" << std::endl;
        ss << "  parsed_action: \"" << to_string(parsed_action) << "\"" << std::endl;
        ss << "  params: [" << to_string(params) << "]" << std::endl;
        ss << "  param_count: " << +param_count << std::endl;
        ss << "  confidence: " << confidence << std::endl;
        ss << "  is_final: " << +is_final << std::endl;
        ss << "  command_id: " << +command_id << std::endl;

        return ss.str();
    }

    inline void serialize(mavlink::MsgMap &map) const override
    {
        map.reset(MSG_ID, LENGTH);

        map << timestamp_ms;                  // offset: 0
        map << params;                        // offset: 4
        map << confidence;                    // offset: 44
        map << command_text;                  // offset: 48
        map << parsed_action;                 // offset: 176
        map << param_count;                   // offset: 208
        map << is_final;                      // offset: 209
        map << command_id;                    // offset: 210
    }

    inline void deserialize(mavlink::MsgMap &map) override
    {
        map >> timestamp_ms;                  // offset: 0
        map >> params;                        // offset: 4
        map >> confidence;                    // offset: 44
        map >> command_text;                  // offset: 48
        map >> parsed_action;                 // offset: 176
        map >> param_count;                   // offset: 208
        map >> is_final;                      // offset: 209
        map >> command_id;                    // offset: 210
    }
};

} // namespace msg
} // namespace voice_control
} // namespace mavlink
