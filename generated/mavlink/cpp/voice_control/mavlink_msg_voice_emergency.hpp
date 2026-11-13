// MESSAGE VOICE_EMERGENCY support class

#pragma once

namespace mavlink {
namespace voice_control {
namespace msg {

/**
 * @brief VOICE_EMERGENCY message
 *
 * Emergency voice command (immediate execution)
 */
struct VOICE_EMERGENCY : mavlink::Message {
    static constexpr msgid_t MSG_ID = 30004;
    static constexpr size_t LENGTH = 25;
    static constexpr size_t MIN_LENGTH = 25;
    static constexpr uint8_t CRC_EXTRA = 249;
    static constexpr auto NAME = "VOICE_EMERGENCY";


    uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot */
    std::array<char, 16> emergency_type; /*<  EMERGENCY_LAND, KILL_MOTORS, RETURN_HOME, ABORT */
    float confidence; /*<  ASR confidence */
    uint8_t source; /*<  0=VOICE, 1=BUTTON, 2=AUTO */


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
        ss << "  emergency_type: \"" << to_string(emergency_type) << "\"" << std::endl;
        ss << "  confidence: " << confidence << std::endl;
        ss << "  source: " << +source << std::endl;

        return ss.str();
    }

    inline void serialize(mavlink::MsgMap &map) const override
    {
        map.reset(MSG_ID, LENGTH);

        map << timestamp_ms;                  // offset: 0
        map << confidence;                    // offset: 4
        map << emergency_type;                // offset: 8
        map << source;                        // offset: 24
    }

    inline void deserialize(mavlink::MsgMap &map) override
    {
        map >> timestamp_ms;                  // offset: 0
        map >> confidence;                    // offset: 4
        map >> emergency_type;                // offset: 8
        map >> source;                        // offset: 24
    }
};

} // namespace msg
} // namespace voice_control
} // namespace mavlink
