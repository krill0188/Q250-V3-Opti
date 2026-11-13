#pragma once
// MESSAGE VOICE_WAYPOINT PACKING

#include <stdint.h>

#define MAVLINK_MSG_ID_VOICE_WAYPOINT 30003


typedef struct __mavlink_voice_waypoint_t {
 uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot*/
 int32_t lat; /*<  Latitude * 1e7*/
 int32_t lon; /*<  Longitude * 1e7*/
 int32_t alt; /*<  Altitude in mm (AMSL)*/
 uint16_t seq; /*<  Waypoint sequence number*/
 uint16_t command_id; /*<  Reference to voice command*/
 char label[32]; /*<  Voice label (e.g., "home", "tree", "landing_pad")*/
 uint8_t frame; /*<  MAV_FRAME enum*/
} mavlink_voice_waypoint_t;

#define MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN 53
#define MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN 53
#define MAVLINK_MSG_ID_30003_LEN 53
#define MAVLINK_MSG_ID_30003_MIN_LEN 53

#define MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC 167
#define MAVLINK_MSG_ID_30003_CRC 167

#define MAVLINK_MSG_VOICE_WAYPOINT_FIELD_LABEL_LEN 32

#if MAVLINK_COMMAND_24BIT
#define MAVLINK_MESSAGE_INFO_VOICE_WAYPOINT { \
    30003, \
    "VOICE_WAYPOINT", \
    8, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_waypoint_t, timestamp_ms) }, \
         { "seq", NULL, MAVLINK_TYPE_UINT16_T, 0, 16, offsetof(mavlink_voice_waypoint_t, seq) }, \
         { "label", NULL, MAVLINK_TYPE_CHAR, 32, 20, offsetof(mavlink_voice_waypoint_t, label) }, \
         { "lat", NULL, MAVLINK_TYPE_INT32_T, 0, 4, offsetof(mavlink_voice_waypoint_t, lat) }, \
         { "lon", NULL, MAVLINK_TYPE_INT32_T, 0, 8, offsetof(mavlink_voice_waypoint_t, lon) }, \
         { "alt", NULL, MAVLINK_TYPE_INT32_T, 0, 12, offsetof(mavlink_voice_waypoint_t, alt) }, \
         { "frame", NULL, MAVLINK_TYPE_UINT8_T, 0, 52, offsetof(mavlink_voice_waypoint_t, frame) }, \
         { "command_id", NULL, MAVLINK_TYPE_UINT16_T, 0, 18, offsetof(mavlink_voice_waypoint_t, command_id) }, \
         } \
}
#else
#define MAVLINK_MESSAGE_INFO_VOICE_WAYPOINT { \
    "VOICE_WAYPOINT", \
    8, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_waypoint_t, timestamp_ms) }, \
         { "seq", NULL, MAVLINK_TYPE_UINT16_T, 0, 16, offsetof(mavlink_voice_waypoint_t, seq) }, \
         { "label", NULL, MAVLINK_TYPE_CHAR, 32, 20, offsetof(mavlink_voice_waypoint_t, label) }, \
         { "lat", NULL, MAVLINK_TYPE_INT32_T, 0, 4, offsetof(mavlink_voice_waypoint_t, lat) }, \
         { "lon", NULL, MAVLINK_TYPE_INT32_T, 0, 8, offsetof(mavlink_voice_waypoint_t, lon) }, \
         { "alt", NULL, MAVLINK_TYPE_INT32_T, 0, 12, offsetof(mavlink_voice_waypoint_t, alt) }, \
         { "frame", NULL, MAVLINK_TYPE_UINT8_T, 0, 52, offsetof(mavlink_voice_waypoint_t, frame) }, \
         { "command_id", NULL, MAVLINK_TYPE_UINT16_T, 0, 18, offsetof(mavlink_voice_waypoint_t, command_id) }, \
         } \
}
#endif

/**
 * @brief Pack a voice_waypoint message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param seq  Waypoint sequence number
 * @param label  Voice label (e.g., "home", "tree", "landing_pad")
 * @param lat  Latitude * 1e7
 * @param lon  Longitude * 1e7
 * @param alt  Altitude in mm (AMSL)
 * @param frame  MAV_FRAME enum
 * @param command_id  Reference to voice command
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_waypoint_pack(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg,
                               uint32_t timestamp_ms, uint16_t seq, const char *label, int32_t lat, int32_t lon, int32_t alt, uint8_t frame, uint16_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_int32_t(buf, 4, lat);
    _mav_put_int32_t(buf, 8, lon);
    _mav_put_int32_t(buf, 12, alt);
    _mav_put_uint16_t(buf, 16, seq);
    _mav_put_uint16_t(buf, 18, command_id);
    _mav_put_uint8_t(buf, 52, frame);
    _mav_put_char_array(buf, 20, label, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN);
#else
    mavlink_voice_waypoint_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.lat = lat;
    packet.lon = lon;
    packet.alt = alt;
    packet.seq = seq;
    packet.command_id = command_id;
    packet.frame = frame;
    mav_array_memcpy(packet.label, label, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_WAYPOINT;
    return mavlink_finalize_message(msg, system_id, component_id, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC);
}

/**
 * @brief Pack a voice_waypoint message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param seq  Waypoint sequence number
 * @param label  Voice label (e.g., "home", "tree", "landing_pad")
 * @param lat  Latitude * 1e7
 * @param lon  Longitude * 1e7
 * @param alt  Altitude in mm (AMSL)
 * @param frame  MAV_FRAME enum
 * @param command_id  Reference to voice command
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_waypoint_pack_status(uint8_t system_id, uint8_t component_id, mavlink_status_t *_status, mavlink_message_t* msg,
                               uint32_t timestamp_ms, uint16_t seq, const char *label, int32_t lat, int32_t lon, int32_t alt, uint8_t frame, uint16_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_int32_t(buf, 4, lat);
    _mav_put_int32_t(buf, 8, lon);
    _mav_put_int32_t(buf, 12, alt);
    _mav_put_uint16_t(buf, 16, seq);
    _mav_put_uint16_t(buf, 18, command_id);
    _mav_put_uint8_t(buf, 52, frame);
    _mav_put_char_array(buf, 20, label, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN);
#else
    mavlink_voice_waypoint_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.lat = lat;
    packet.lon = lon;
    packet.alt = alt;
    packet.seq = seq;
    packet.command_id = command_id;
    packet.frame = frame;
    mav_array_memcpy(packet.label, label, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_WAYPOINT;
#if MAVLINK_CRC_EXTRA
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC);
#else
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN);
#endif
}

/**
 * @brief Pack a voice_waypoint message on a channel
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param seq  Waypoint sequence number
 * @param label  Voice label (e.g., "home", "tree", "landing_pad")
 * @param lat  Latitude * 1e7
 * @param lon  Longitude * 1e7
 * @param alt  Altitude in mm (AMSL)
 * @param frame  MAV_FRAME enum
 * @param command_id  Reference to voice command
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_waypoint_pack_chan(uint8_t system_id, uint8_t component_id, uint8_t chan,
                               mavlink_message_t* msg,
                                   uint32_t timestamp_ms,uint16_t seq,const char *label,int32_t lat,int32_t lon,int32_t alt,uint8_t frame,uint16_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_int32_t(buf, 4, lat);
    _mav_put_int32_t(buf, 8, lon);
    _mav_put_int32_t(buf, 12, alt);
    _mav_put_uint16_t(buf, 16, seq);
    _mav_put_uint16_t(buf, 18, command_id);
    _mav_put_uint8_t(buf, 52, frame);
    _mav_put_char_array(buf, 20, label, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN);
#else
    mavlink_voice_waypoint_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.lat = lat;
    packet.lon = lon;
    packet.alt = alt;
    packet.seq = seq;
    packet.command_id = command_id;
    packet.frame = frame;
    mav_array_memcpy(packet.label, label, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_WAYPOINT;
    return mavlink_finalize_message_chan(msg, system_id, component_id, chan, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC);
}

/**
 * @brief Encode a voice_waypoint struct
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 * @param voice_waypoint C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_waypoint_encode(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg, const mavlink_voice_waypoint_t* voice_waypoint)
{
    return mavlink_msg_voice_waypoint_pack(system_id, component_id, msg, voice_waypoint->timestamp_ms, voice_waypoint->seq, voice_waypoint->label, voice_waypoint->lat, voice_waypoint->lon, voice_waypoint->alt, voice_waypoint->frame, voice_waypoint->command_id);
}

/**
 * @brief Encode a voice_waypoint struct on a channel
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param voice_waypoint C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_waypoint_encode_chan(uint8_t system_id, uint8_t component_id, uint8_t chan, mavlink_message_t* msg, const mavlink_voice_waypoint_t* voice_waypoint)
{
    return mavlink_msg_voice_waypoint_pack_chan(system_id, component_id, chan, msg, voice_waypoint->timestamp_ms, voice_waypoint->seq, voice_waypoint->label, voice_waypoint->lat, voice_waypoint->lon, voice_waypoint->alt, voice_waypoint->frame, voice_waypoint->command_id);
}

/**
 * @brief Encode a voice_waypoint struct with provided status structure
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 * @param voice_waypoint C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_waypoint_encode_status(uint8_t system_id, uint8_t component_id, mavlink_status_t* _status, mavlink_message_t* msg, const mavlink_voice_waypoint_t* voice_waypoint)
{
    return mavlink_msg_voice_waypoint_pack_status(system_id, component_id, _status, msg,  voice_waypoint->timestamp_ms, voice_waypoint->seq, voice_waypoint->label, voice_waypoint->lat, voice_waypoint->lon, voice_waypoint->alt, voice_waypoint->frame, voice_waypoint->command_id);
}

/**
 * @brief Send a voice_waypoint message
 * @param chan MAVLink channel to send the message
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param seq  Waypoint sequence number
 * @param label  Voice label (e.g., "home", "tree", "landing_pad")
 * @param lat  Latitude * 1e7
 * @param lon  Longitude * 1e7
 * @param alt  Altitude in mm (AMSL)
 * @param frame  MAV_FRAME enum
 * @param command_id  Reference to voice command
 */
#ifdef MAVLINK_USE_CONVENIENCE_FUNCTIONS

static inline void mavlink_msg_voice_waypoint_send(mavlink_channel_t chan, uint32_t timestamp_ms, uint16_t seq, const char *label, int32_t lat, int32_t lon, int32_t alt, uint8_t frame, uint16_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_int32_t(buf, 4, lat);
    _mav_put_int32_t(buf, 8, lon);
    _mav_put_int32_t(buf, 12, alt);
    _mav_put_uint16_t(buf, 16, seq);
    _mav_put_uint16_t(buf, 18, command_id);
    _mav_put_uint8_t(buf, 52, frame);
    _mav_put_char_array(buf, 20, label, 32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_WAYPOINT, buf, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC);
#else
    mavlink_voice_waypoint_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.lat = lat;
    packet.lon = lon;
    packet.alt = alt;
    packet.seq = seq;
    packet.command_id = command_id;
    packet.frame = frame;
    mav_array_memcpy(packet.label, label, sizeof(char)*32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_WAYPOINT, (const char *)&packet, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC);
#endif
}

/**
 * @brief Send a voice_waypoint message
 * @param chan MAVLink channel to send the message
 * @param struct The MAVLink struct to serialize
 */
static inline void mavlink_msg_voice_waypoint_send_struct(mavlink_channel_t chan, const mavlink_voice_waypoint_t* voice_waypoint)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    mavlink_msg_voice_waypoint_send(chan, voice_waypoint->timestamp_ms, voice_waypoint->seq, voice_waypoint->label, voice_waypoint->lat, voice_waypoint->lon, voice_waypoint->alt, voice_waypoint->frame, voice_waypoint->command_id);
#else
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_WAYPOINT, (const char *)voice_waypoint, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC);
#endif
}

#if MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN <= MAVLINK_MAX_PAYLOAD_LEN
/*
  This variant of _send() can be used to save stack space by reusing
  memory from the receive buffer.  The caller provides a
  mavlink_message_t which is the size of a full mavlink message. This
  is usually the receive buffer for the channel, and allows a reply to an
  incoming message with minimum stack space usage.
 */
static inline void mavlink_msg_voice_waypoint_send_buf(mavlink_message_t *msgbuf, mavlink_channel_t chan,  uint32_t timestamp_ms, uint16_t seq, const char *label, int32_t lat, int32_t lon, int32_t alt, uint8_t frame, uint16_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char *buf = (char *)msgbuf;
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_int32_t(buf, 4, lat);
    _mav_put_int32_t(buf, 8, lon);
    _mav_put_int32_t(buf, 12, alt);
    _mav_put_uint16_t(buf, 16, seq);
    _mav_put_uint16_t(buf, 18, command_id);
    _mav_put_uint8_t(buf, 52, frame);
    _mav_put_char_array(buf, 20, label, 32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_WAYPOINT, buf, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC);
#else
    mavlink_voice_waypoint_t *packet = (mavlink_voice_waypoint_t *)msgbuf;
    packet->timestamp_ms = timestamp_ms;
    packet->lat = lat;
    packet->lon = lon;
    packet->alt = alt;
    packet->seq = seq;
    packet->command_id = command_id;
    packet->frame = frame;
    mav_array_memcpy(packet->label, label, sizeof(char)*32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_WAYPOINT, (const char *)packet, MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN, MAVLINK_MSG_ID_VOICE_WAYPOINT_CRC);
#endif
}
#endif

#endif

// MESSAGE VOICE_WAYPOINT UNPACKING


/**
 * @brief Get field timestamp_ms from voice_waypoint message
 *
 * @return  Timestamp in milliseconds since boot
 */
static inline uint32_t mavlink_msg_voice_waypoint_get_timestamp_ms(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint32_t(msg,  0);
}

/**
 * @brief Get field seq from voice_waypoint message
 *
 * @return  Waypoint sequence number
 */
static inline uint16_t mavlink_msg_voice_waypoint_get_seq(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint16_t(msg,  16);
}

/**
 * @brief Get field label from voice_waypoint message
 *
 * @return  Voice label (e.g., "home", "tree", "landing_pad")
 */
static inline uint16_t mavlink_msg_voice_waypoint_get_label(const mavlink_message_t* msg, char *label)
{
    return _MAV_RETURN_char_array(msg, label, 32,  20);
}

/**
 * @brief Get field lat from voice_waypoint message
 *
 * @return  Latitude * 1e7
 */
static inline int32_t mavlink_msg_voice_waypoint_get_lat(const mavlink_message_t* msg)
{
    return _MAV_RETURN_int32_t(msg,  4);
}

/**
 * @brief Get field lon from voice_waypoint message
 *
 * @return  Longitude * 1e7
 */
static inline int32_t mavlink_msg_voice_waypoint_get_lon(const mavlink_message_t* msg)
{
    return _MAV_RETURN_int32_t(msg,  8);
}

/**
 * @brief Get field alt from voice_waypoint message
 *
 * @return  Altitude in mm (AMSL)
 */
static inline int32_t mavlink_msg_voice_waypoint_get_alt(const mavlink_message_t* msg)
{
    return _MAV_RETURN_int32_t(msg,  12);
}

/**
 * @brief Get field frame from voice_waypoint message
 *
 * @return  MAV_FRAME enum
 */
static inline uint8_t mavlink_msg_voice_waypoint_get_frame(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  52);
}

/**
 * @brief Get field command_id from voice_waypoint message
 *
 * @return  Reference to voice command
 */
static inline uint16_t mavlink_msg_voice_waypoint_get_command_id(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint16_t(msg,  18);
}

/**
 * @brief Decode a voice_waypoint message into a struct
 *
 * @param msg The message to decode
 * @param voice_waypoint C-struct to decode the message contents into
 */
static inline void mavlink_msg_voice_waypoint_decode(const mavlink_message_t* msg, mavlink_voice_waypoint_t* voice_waypoint)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    voice_waypoint->timestamp_ms = mavlink_msg_voice_waypoint_get_timestamp_ms(msg);
    voice_waypoint->lat = mavlink_msg_voice_waypoint_get_lat(msg);
    voice_waypoint->lon = mavlink_msg_voice_waypoint_get_lon(msg);
    voice_waypoint->alt = mavlink_msg_voice_waypoint_get_alt(msg);
    voice_waypoint->seq = mavlink_msg_voice_waypoint_get_seq(msg);
    voice_waypoint->command_id = mavlink_msg_voice_waypoint_get_command_id(msg);
    mavlink_msg_voice_waypoint_get_label(msg, voice_waypoint->label);
    voice_waypoint->frame = mavlink_msg_voice_waypoint_get_frame(msg);
#else
        uint8_t len = msg->len < MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN? msg->len : MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN;
        memset(voice_waypoint, 0, MAVLINK_MSG_ID_VOICE_WAYPOINT_LEN);
    memcpy(voice_waypoint, _MAV_PAYLOAD(msg), len);
#endif
}
