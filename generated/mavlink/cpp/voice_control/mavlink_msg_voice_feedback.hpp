// MESSAGE VOICE_FEEDBACK support class

#pragma once

namespace mavlink {
namespace voice_control {
namespace msg {

/**
 * @brief VOICE_FEEDBACK message
 *
 * Voice feedback from drone to GCS
 */
struct VOICE_FEEDBACK : mavlink::Message {
    static constexpr msgid_t MSG_ID = 30002;
    static constexpr size_t LENGTH = 74;
    static constexpr size_t MIN_LENGTH = 74;
    static constexpr uint8_t CRC_EXTRA = 30;
    static constexpr auto NAME = "VOICE_FEEDBACK";


    uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot */
    uint8_t feedback_type; /*<  0=ACK, 1=EXECUTING, 2=COMPLETED, 3=FAILED, 4=REJECTED */
    uint8_t command_id; /*<  Reference to original command */
    std::array<char, 64> message; /*<  Human readable feedback */
    float progress; /*<  Execution progress 0.0-1.0 */


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
        ss << "  feedback_type: " << +feedback_type << std::endl;
        ss << "  command_id: " << +command_id << std::endl;
        ss << "  message: \"" << to_string(message) << "\"" << std::endl;
        ss << "  progress: " << progress << std::endl;

        return ss.str();
    }

    inline void serialize(mavlink::MsgMap &map) const override
    {
        map.reset(MSG_ID, LENGTH);

        map << timestamp_ms;                  // offset: 0
        map << progress;                      // offset: 4
        map << feedback_type;                 // offset: 8
        map << command_id;                    // offset: 9
        map << message;                       // offset: 10
    }

    inline void deserialize(mavlink::MsgMap &map) override
    {
        map >> timestamp_ms;                  // offset: 0
        map >> progress;                      // offset: 4
        map >> feedback_type;                 // offset: 8
        map >> command_id;                    // offset: 9
        map >> message;                       // offset: 10
    }
};

} // namespace msg
} // namespace voice_control
} // namespace mavlink
