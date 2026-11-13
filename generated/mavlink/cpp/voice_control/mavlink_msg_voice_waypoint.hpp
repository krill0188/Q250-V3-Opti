// MESSAGE VOICE_WAYPOINT support class

#pragma once

namespace mavlink {
namespace voice_control {
namespace msg {

/**
 * @brief VOICE_WAYPOINT message
 *
 * Voice-defined waypoint
 */
struct VOICE_WAYPOINT : mavlink::Message {
    static constexpr msgid_t MSG_ID = 30003;
    static constexpr size_t LENGTH = 53;
    static constexpr size_t MIN_LENGTH = 53;
    static constexpr uint8_t CRC_EXTRA = 167;
    static constexpr auto NAME = "VOICE_WAYPOINT";


    uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot */
    uint16_t seq; /*<  Waypoint sequence number */
    std::array<char, 32> label; /*<  Voice label (e.g., "home", "tree", "landing_pad") */
    int32_t lat; /*<  Latitude * 1e7 */
    int32_t lon; /*<  Longitude * 1e7 */
    int32_t alt; /*<  Altitude in mm (AMSL) */
    uint8_t frame; /*<  MAV_FRAME enum */
    uint16_t command_id; /*<  Reference to voice command */


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
        ss << "  seq: " << seq << std::endl;
        ss << "  label: \"" << to_string(label) << "\"" << std::endl;
        ss << "  lat: " << lat << std::endl;
        ss << "  lon: " << lon << std::endl;
        ss << "  alt: " << alt << std::endl;
        ss << "  frame: " << +frame << std::endl;
        ss << "  command_id: " << command_id << std::endl;

        return ss.str();
    }

    inline void serialize(mavlink::MsgMap &map) const override
    {
        map.reset(MSG_ID, LENGTH);

        map << timestamp_ms;                  // offset: 0
        map << lat;                           // offset: 4
        map << lon;                           // offset: 8
        map << alt;                           // offset: 12
        map << seq;                           // offset: 16
        map << command_id;                    // offset: 18
        map << label;                         // offset: 20
        map << frame;                         // offset: 52
    }

    inline void deserialize(mavlink::MsgMap &map) override
    {
        map >> timestamp_ms;                  // offset: 0
        map >> lat;                           // offset: 4
        map >> lon;                           // offset: 8
        map >> alt;                           // offset: 12
        map >> seq;                           // offset: 16
        map >> command_id;                    // offset: 18
        map >> label;                         // offset: 20
        map >> frame;                         // offset: 52
    }
};

} // namespace msg
} // namespace voice_control
} // namespace mavlink
