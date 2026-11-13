#pragma once
// MESSAGE VOICE_EMERGENCY PACKING

#include <stdint.h>

#define MAVLINK_MSG_ID_VOICE_EMERGENCY 30004


typedef struct __mavlink_voice_emergency_t {
 uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot*/
 float confidence; /*<  ASR confidence*/
 char emergency_type[16]; /*<  EMERGENCY_LAND, KILL_MOTORS, RETURN_HOME, ABORT*/
 uint8_t source; /*<  0=VOICE, 1=BUTTON, 2=AUTO*/
} mavlink_voice_emergency_t;

#define MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN 25
#define MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN 25
#define MAVLINK_MSG_ID_30004_LEN 25
#define MAVLINK_MSG_ID_30004_MIN_LEN 25

#define MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC 249
#define MAVLINK_MSG_ID_30004_CRC 249

#define MAVLINK_MSG_VOICE_EMERGENCY_FIELD_EMERGENCY_TYPE_LEN 16

#if MAVLINK_COMMAND_24BIT
#define MAVLINK_MESSAGE_INFO_VOICE_EMERGENCY { \
    30004, \
    "VOICE_EMERGENCY", \
    4, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_emergency_t, timestamp_ms) }, \
         { "emergency_type", NULL, MAVLINK_TYPE_CHAR, 16, 8, offsetof(mavlink_voice_emergency_t, emergency_type) }, \
         { "confidence", NULL, MAVLINK_TYPE_FLOAT, 0, 4, offsetof(mavlink_voice_emergency_t, confidence) }, \
         { "source", NULL, MAVLINK_TYPE_UINT8_T, 0, 24, offsetof(mavlink_voice_emergency_t, source) }, \
         } \
}
#else
#define MAVLINK_MESSAGE_INFO_VOICE_EMERGENCY { \
    "VOICE_EMERGENCY", \
    4, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_emergency_t, timestamp_ms) }, \
         { "emergency_type", NULL, MAVLINK_TYPE_CHAR, 16, 8, offsetof(mavlink_voice_emergency_t, emergency_type) }, \
         { "confidence", NULL, MAVLINK_TYPE_FLOAT, 0, 4, offsetof(mavlink_voice_emergency_t, confidence) }, \
         { "source", NULL, MAVLINK_TYPE_UINT8_T, 0, 24, offsetof(mavlink_voice_emergency_t, source) }, \
         } \
}
#endif

/**
 * @brief Pack a voice_emergency message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param emergency_type  EMERGENCY_LAND, KILL_MOTORS, RETURN_HOME, ABORT
 * @param confidence  ASR confidence
 * @param source  0=VOICE, 1=BUTTON, 2=AUTO
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_emergency_pack(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg,
                               uint32_t timestamp_ms, const char *emergency_type, float confidence, uint8_t source)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, confidence);
    _mav_put_uint8_t(buf, 24, source);
    _mav_put_char_array(buf, 8, emergency_type, 16);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN);
#else
    mavlink_voice_emergency_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.confidence = confidence;
    packet.source = source;
    mav_array_memcpy(packet.emergency_type, emergency_type, sizeof(char)*16);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_EMERGENCY;
    return mavlink_finalize_message(msg, system_id, component_id, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC);
}

/**
 * @brief Pack a voice_emergency message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param emergency_type  EMERGENCY_LAND, KILL_MOTORS, RETURN_HOME, ABORT
 * @param confidence  ASR confidence
 * @param source  0=VOICE, 1=BUTTON, 2=AUTO
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_emergency_pack_status(uint8_t system_id, uint8_t component_id, mavlink_status_t *_status, mavlink_message_t* msg,
                               uint32_t timestamp_ms, const char *emergency_type, float confidence, uint8_t source)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, confidence);
    _mav_put_uint8_t(buf, 24, source);
    _mav_put_char_array(buf, 8, emergency_type, 16);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN);
#else
    mavlink_voice_emergency_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.confidence = confidence;
    packet.source = source;
    mav_array_memcpy(packet.emergency_type, emergency_type, sizeof(char)*16);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_EMERGENCY;
#if MAVLINK_CRC_EXTRA
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC);
#else
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN);
#endif
}

/**
 * @brief Pack a voice_emergency message on a channel
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param emergency_type  EMERGENCY_LAND, KILL_MOTORS, RETURN_HOME, ABORT
 * @param confidence  ASR confidence
 * @param source  0=VOICE, 1=BUTTON, 2=AUTO
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_emergency_pack_chan(uint8_t system_id, uint8_t component_id, uint8_t chan,
                               mavlink_message_t* msg,
                                   uint32_t timestamp_ms,const char *emergency_type,float confidence,uint8_t source)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, confidence);
    _mav_put_uint8_t(buf, 24, source);
    _mav_put_char_array(buf, 8, emergency_type, 16);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN);
#else
    mavlink_voice_emergency_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.confidence = confidence;
    packet.source = source;
    mav_array_memcpy(packet.emergency_type, emergency_type, sizeof(char)*16);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_EMERGENCY;
    return mavlink_finalize_message_chan(msg, system_id, component_id, chan, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC);
}

/**
 * @brief Encode a voice_emergency struct
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 * @param voice_emergency C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_emergency_encode(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg, const mavlink_voice_emergency_t* voice_emergency)
{
    return mavlink_msg_voice_emergency_pack(system_id, component_id, msg, voice_emergency->timestamp_ms, voice_emergency->emergency_type, voice_emergency->confidence, voice_emergency->source);
}

/**
 * @brief Encode a voice_emergency struct on a channel
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param voice_emergency C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_emergency_encode_chan(uint8_t system_id, uint8_t component_id, uint8_t chan, mavlink_message_t* msg, const mavlink_voice_emergency_t* voice_emergency)
{
    return mavlink_msg_voice_emergency_pack_chan(system_id, component_id, chan, msg, voice_emergency->timestamp_ms, voice_emergency->emergency_type, voice_emergency->confidence, voice_emergency->source);
}

/**
 * @brief Encode a voice_emergency struct with provided status structure
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 * @param voice_emergency C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_emergency_encode_status(uint8_t system_id, uint8_t component_id, mavlink_status_t* _status, mavlink_message_t* msg, const mavlink_voice_emergency_t* voice_emergency)
{
    return mavlink_msg_voice_emergency_pack_status(system_id, component_id, _status, msg,  voice_emergency->timestamp_ms, voice_emergency->emergency_type, voice_emergency->confidence, voice_emergency->source);
}

/**
 * @brief Send a voice_emergency message
 * @param chan MAVLink channel to send the message
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param emergency_type  EMERGENCY_LAND, KILL_MOTORS, RETURN_HOME, ABORT
 * @param confidence  ASR confidence
 * @param source  0=VOICE, 1=BUTTON, 2=AUTO
 */
#ifdef MAVLINK_USE_CONVENIENCE_FUNCTIONS

static inline void mavlink_msg_voice_emergency_send(mavlink_channel_t chan, uint32_t timestamp_ms, const char *emergency_type, float confidence, uint8_t source)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, confidence);
    _mav_put_uint8_t(buf, 24, source);
    _mav_put_char_array(buf, 8, emergency_type, 16);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_EMERGENCY, buf, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC);
#else
    mavlink_voice_emergency_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.confidence = confidence;
    packet.source = source;
    mav_array_memcpy(packet.emergency_type, emergency_type, sizeof(char)*16);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_EMERGENCY, (const char *)&packet, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC);
#endif
}

/**
 * @brief Send a voice_emergency message
 * @param chan MAVLink channel to send the message
 * @param struct The MAVLink struct to serialize
 */
static inline void mavlink_msg_voice_emergency_send_struct(mavlink_channel_t chan, const mavlink_voice_emergency_t* voice_emergency)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    mavlink_msg_voice_emergency_send(chan, voice_emergency->timestamp_ms, voice_emergency->emergency_type, voice_emergency->confidence, voice_emergency->source);
#else
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_EMERGENCY, (const char *)voice_emergency, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC);
#endif
}

#if MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN <= MAVLINK_MAX_PAYLOAD_LEN
/*
  This variant of _send() can be used to save stack space by reusing
  memory from the receive buffer.  The caller provides a
  mavlink_message_t which is the size of a full mavlink message. This
  is usually the receive buffer for the channel, and allows a reply to an
  incoming message with minimum stack space usage.
 */
static inline void mavlink_msg_voice_emergency_send_buf(mavlink_message_t *msgbuf, mavlink_channel_t chan,  uint32_t timestamp_ms, const char *emergency_type, float confidence, uint8_t source)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char *buf = (char *)msgbuf;
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, confidence);
    _mav_put_uint8_t(buf, 24, source);
    _mav_put_char_array(buf, 8, emergency_type, 16);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_EMERGENCY, buf, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC);
#else
    mavlink_voice_emergency_t *packet = (mavlink_voice_emergency_t *)msgbuf;
    packet->timestamp_ms = timestamp_ms;
    packet->confidence = confidence;
    packet->source = source;
    mav_array_memcpy(packet->emergency_type, emergency_type, sizeof(char)*16);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_EMERGENCY, (const char *)packet, MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN, MAVLINK_MSG_ID_VOICE_EMERGENCY_CRC);
#endif
}
#endif

#endif

// MESSAGE VOICE_EMERGENCY UNPACKING


/**
 * @brief Get field timestamp_ms from voice_emergency message
 *
 * @return  Timestamp in milliseconds since boot
 */
static inline uint32_t mavlink_msg_voice_emergency_get_timestamp_ms(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint32_t(msg,  0);
}

/**
 * @brief Get field emergency_type from voice_emergency message
 *
 * @return  EMERGENCY_LAND, KILL_MOTORS, RETURN_HOME, ABORT
 */
static inline uint16_t mavlink_msg_voice_emergency_get_emergency_type(const mavlink_message_t* msg, char *emergency_type)
{
    return _MAV_RETURN_char_array(msg, emergency_type, 16,  8);
}

/**
 * @brief Get field confidence from voice_emergency message
 *
 * @return  ASR confidence
 */
static inline float mavlink_msg_voice_emergency_get_confidence(const mavlink_message_t* msg)
{
    return _MAV_RETURN_float(msg,  4);
}

/**
 * @brief Get field source from voice_emergency message
 *
 * @return  0=VOICE, 1=BUTTON, 2=AUTO
 */
static inline uint8_t mavlink_msg_voice_emergency_get_source(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  24);
}

/**
 * @brief Decode a voice_emergency message into a struct
 *
 * @param msg The message to decode
 * @param voice_emergency C-struct to decode the message contents into
 */
static inline void mavlink_msg_voice_emergency_decode(const mavlink_message_t* msg, mavlink_voice_emergency_t* voice_emergency)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    voice_emergency->timestamp_ms = mavlink_msg_voice_emergency_get_timestamp_ms(msg);
    voice_emergency->confidence = mavlink_msg_voice_emergency_get_confidence(msg);
    mavlink_msg_voice_emergency_get_emergency_type(msg, voice_emergency->emergency_type);
    voice_emergency->source = mavlink_msg_voice_emergency_get_source(msg);
#else
        uint8_t len = msg->len < MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN? msg->len : MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN;
        memset(voice_emergency, 0, MAVLINK_MSG_ID_VOICE_EMERGENCY_LEN);
    memcpy(voice_emergency, _MAV_PAYLOAD(msg), len);
#endif
}
