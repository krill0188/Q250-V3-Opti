#pragma once
// MESSAGE VOICE_FEEDBACK PACKING

#include <stdint.h>

#define MAVLINK_MSG_ID_VOICE_FEEDBACK 30002


typedef struct __mavlink_voice_feedback_t {
 uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot*/
 float progress; /*<  Execution progress 0.0-1.0*/
 uint8_t feedback_type; /*<  0=ACK, 1=EXECUTING, 2=COMPLETED, 3=FAILED, 4=REJECTED*/
 uint8_t command_id; /*<  Reference to original command*/
 char message[64]; /*<  Human readable feedback*/
} mavlink_voice_feedback_t;

#define MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN 74
#define MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN 74
#define MAVLINK_MSG_ID_30002_LEN 74
#define MAVLINK_MSG_ID_30002_MIN_LEN 74

#define MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC 30
#define MAVLINK_MSG_ID_30002_CRC 30

#define MAVLINK_MSG_VOICE_FEEDBACK_FIELD_MESSAGE_LEN 64

#if MAVLINK_COMMAND_24BIT
#define MAVLINK_MESSAGE_INFO_VOICE_FEEDBACK { \
    30002, \
    "VOICE_FEEDBACK", \
    5, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_feedback_t, timestamp_ms) }, \
         { "feedback_type", NULL, MAVLINK_TYPE_UINT8_T, 0, 8, offsetof(mavlink_voice_feedback_t, feedback_type) }, \
         { "command_id", NULL, MAVLINK_TYPE_UINT8_T, 0, 9, offsetof(mavlink_voice_feedback_t, command_id) }, \
         { "message", NULL, MAVLINK_TYPE_CHAR, 64, 10, offsetof(mavlink_voice_feedback_t, message) }, \
         { "progress", NULL, MAVLINK_TYPE_FLOAT, 0, 4, offsetof(mavlink_voice_feedback_t, progress) }, \
         } \
}
#else
#define MAVLINK_MESSAGE_INFO_VOICE_FEEDBACK { \
    "VOICE_FEEDBACK", \
    5, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_feedback_t, timestamp_ms) }, \
         { "feedback_type", NULL, MAVLINK_TYPE_UINT8_T, 0, 8, offsetof(mavlink_voice_feedback_t, feedback_type) }, \
         { "command_id", NULL, MAVLINK_TYPE_UINT8_T, 0, 9, offsetof(mavlink_voice_feedback_t, command_id) }, \
         { "message", NULL, MAVLINK_TYPE_CHAR, 64, 10, offsetof(mavlink_voice_feedback_t, message) }, \
         { "progress", NULL, MAVLINK_TYPE_FLOAT, 0, 4, offsetof(mavlink_voice_feedback_t, progress) }, \
         } \
}
#endif

/**
 * @brief Pack a voice_feedback message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param feedback_type  0=ACK, 1=EXECUTING, 2=COMPLETED, 3=FAILED, 4=REJECTED
 * @param command_id  Reference to original command
 * @param message  Human readable feedback
 * @param progress  Execution progress 0.0-1.0
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_feedback_pack(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg,
                               uint32_t timestamp_ms, uint8_t feedback_type, uint8_t command_id, const char *message, float progress)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, progress);
    _mav_put_uint8_t(buf, 8, feedback_type);
    _mav_put_uint8_t(buf, 9, command_id);
    _mav_put_char_array(buf, 10, message, 64);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN);
#else
    mavlink_voice_feedback_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.progress = progress;
    packet.feedback_type = feedback_type;
    packet.command_id = command_id;
    mav_array_memcpy(packet.message, message, sizeof(char)*64);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_FEEDBACK;
    return mavlink_finalize_message(msg, system_id, component_id, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC);
}

/**
 * @brief Pack a voice_feedback message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param feedback_type  0=ACK, 1=EXECUTING, 2=COMPLETED, 3=FAILED, 4=REJECTED
 * @param command_id  Reference to original command
 * @param message  Human readable feedback
 * @param progress  Execution progress 0.0-1.0
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_feedback_pack_status(uint8_t system_id, uint8_t component_id, mavlink_status_t *_status, mavlink_message_t* msg,
                               uint32_t timestamp_ms, uint8_t feedback_type, uint8_t command_id, const char *message, float progress)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, progress);
    _mav_put_uint8_t(buf, 8, feedback_type);
    _mav_put_uint8_t(buf, 9, command_id);
    _mav_put_char_array(buf, 10, message, 64);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN);
#else
    mavlink_voice_feedback_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.progress = progress;
    packet.feedback_type = feedback_type;
    packet.command_id = command_id;
    mav_array_memcpy(packet.message, message, sizeof(char)*64);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_FEEDBACK;
#if MAVLINK_CRC_EXTRA
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC);
#else
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN);
#endif
}

/**
 * @brief Pack a voice_feedback message on a channel
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param feedback_type  0=ACK, 1=EXECUTING, 2=COMPLETED, 3=FAILED, 4=REJECTED
 * @param command_id  Reference to original command
 * @param message  Human readable feedback
 * @param progress  Execution progress 0.0-1.0
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_feedback_pack_chan(uint8_t system_id, uint8_t component_id, uint8_t chan,
                               mavlink_message_t* msg,
                                   uint32_t timestamp_ms,uint8_t feedback_type,uint8_t command_id,const char *message,float progress)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, progress);
    _mav_put_uint8_t(buf, 8, feedback_type);
    _mav_put_uint8_t(buf, 9, command_id);
    _mav_put_char_array(buf, 10, message, 64);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN);
#else
    mavlink_voice_feedback_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.progress = progress;
    packet.feedback_type = feedback_type;
    packet.command_id = command_id;
    mav_array_memcpy(packet.message, message, sizeof(char)*64);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_FEEDBACK;
    return mavlink_finalize_message_chan(msg, system_id, component_id, chan, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC);
}

/**
 * @brief Encode a voice_feedback struct
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 * @param voice_feedback C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_feedback_encode(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg, const mavlink_voice_feedback_t* voice_feedback)
{
    return mavlink_msg_voice_feedback_pack(system_id, component_id, msg, voice_feedback->timestamp_ms, voice_feedback->feedback_type, voice_feedback->command_id, voice_feedback->message, voice_feedback->progress);
}

/**
 * @brief Encode a voice_feedback struct on a channel
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param voice_feedback C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_feedback_encode_chan(uint8_t system_id, uint8_t component_id, uint8_t chan, mavlink_message_t* msg, const mavlink_voice_feedback_t* voice_feedback)
{
    return mavlink_msg_voice_feedback_pack_chan(system_id, component_id, chan, msg, voice_feedback->timestamp_ms, voice_feedback->feedback_type, voice_feedback->command_id, voice_feedback->message, voice_feedback->progress);
}

/**
 * @brief Encode a voice_feedback struct with provided status structure
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 * @param voice_feedback C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_feedback_encode_status(uint8_t system_id, uint8_t component_id, mavlink_status_t* _status, mavlink_message_t* msg, const mavlink_voice_feedback_t* voice_feedback)
{
    return mavlink_msg_voice_feedback_pack_status(system_id, component_id, _status, msg,  voice_feedback->timestamp_ms, voice_feedback->feedback_type, voice_feedback->command_id, voice_feedback->message, voice_feedback->progress);
}

/**
 * @brief Send a voice_feedback message
 * @param chan MAVLink channel to send the message
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param feedback_type  0=ACK, 1=EXECUTING, 2=COMPLETED, 3=FAILED, 4=REJECTED
 * @param command_id  Reference to original command
 * @param message  Human readable feedback
 * @param progress  Execution progress 0.0-1.0
 */
#ifdef MAVLINK_USE_CONVENIENCE_FUNCTIONS

static inline void mavlink_msg_voice_feedback_send(mavlink_channel_t chan, uint32_t timestamp_ms, uint8_t feedback_type, uint8_t command_id, const char *message, float progress)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, progress);
    _mav_put_uint8_t(buf, 8, feedback_type);
    _mav_put_uint8_t(buf, 9, command_id);
    _mav_put_char_array(buf, 10, message, 64);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_FEEDBACK, buf, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC);
#else
    mavlink_voice_feedback_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.progress = progress;
    packet.feedback_type = feedback_type;
    packet.command_id = command_id;
    mav_array_memcpy(packet.message, message, sizeof(char)*64);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_FEEDBACK, (const char *)&packet, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC);
#endif
}

/**
 * @brief Send a voice_feedback message
 * @param chan MAVLink channel to send the message
 * @param struct The MAVLink struct to serialize
 */
static inline void mavlink_msg_voice_feedback_send_struct(mavlink_channel_t chan, const mavlink_voice_feedback_t* voice_feedback)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    mavlink_msg_voice_feedback_send(chan, voice_feedback->timestamp_ms, voice_feedback->feedback_type, voice_feedback->command_id, voice_feedback->message, voice_feedback->progress);
#else
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_FEEDBACK, (const char *)voice_feedback, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC);
#endif
}

#if MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN <= MAVLINK_MAX_PAYLOAD_LEN
/*
  This variant of _send() can be used to save stack space by reusing
  memory from the receive buffer.  The caller provides a
  mavlink_message_t which is the size of a full mavlink message. This
  is usually the receive buffer for the channel, and allows a reply to an
  incoming message with minimum stack space usage.
 */
static inline void mavlink_msg_voice_feedback_send_buf(mavlink_message_t *msgbuf, mavlink_channel_t chan,  uint32_t timestamp_ms, uint8_t feedback_type, uint8_t command_id, const char *message, float progress)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char *buf = (char *)msgbuf;
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, progress);
    _mav_put_uint8_t(buf, 8, feedback_type);
    _mav_put_uint8_t(buf, 9, command_id);
    _mav_put_char_array(buf, 10, message, 64);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_FEEDBACK, buf, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC);
#else
    mavlink_voice_feedback_t *packet = (mavlink_voice_feedback_t *)msgbuf;
    packet->timestamp_ms = timestamp_ms;
    packet->progress = progress;
    packet->feedback_type = feedback_type;
    packet->command_id = command_id;
    mav_array_memcpy(packet->message, message, sizeof(char)*64);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_FEEDBACK, (const char *)packet, MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN, MAVLINK_MSG_ID_VOICE_FEEDBACK_CRC);
#endif
}
#endif

#endif

// MESSAGE VOICE_FEEDBACK UNPACKING


/**
 * @brief Get field timestamp_ms from voice_feedback message
 *
 * @return  Timestamp in milliseconds since boot
 */
static inline uint32_t mavlink_msg_voice_feedback_get_timestamp_ms(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint32_t(msg,  0);
}

/**
 * @brief Get field feedback_type from voice_feedback message
 *
 * @return  0=ACK, 1=EXECUTING, 2=COMPLETED, 3=FAILED, 4=REJECTED
 */
static inline uint8_t mavlink_msg_voice_feedback_get_feedback_type(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  8);
}

/**
 * @brief Get field command_id from voice_feedback message
 *
 * @return  Reference to original command
 */
static inline uint8_t mavlink_msg_voice_feedback_get_command_id(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  9);
}

/**
 * @brief Get field message from voice_feedback message
 *
 * @return  Human readable feedback
 */
static inline uint16_t mavlink_msg_voice_feedback_get_message(const mavlink_message_t* msg, char *message)
{
    return _MAV_RETURN_char_array(msg, message, 64,  10);
}

/**
 * @brief Get field progress from voice_feedback message
 *
 * @return  Execution progress 0.0-1.0
 */
static inline float mavlink_msg_voice_feedback_get_progress(const mavlink_message_t* msg)
{
    return _MAV_RETURN_float(msg,  4);
}

/**
 * @brief Decode a voice_feedback message into a struct
 *
 * @param msg The message to decode
 * @param voice_feedback C-struct to decode the message contents into
 */
static inline void mavlink_msg_voice_feedback_decode(const mavlink_message_t* msg, mavlink_voice_feedback_t* voice_feedback)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    voice_feedback->timestamp_ms = mavlink_msg_voice_feedback_get_timestamp_ms(msg);
    voice_feedback->progress = mavlink_msg_voice_feedback_get_progress(msg);
    voice_feedback->feedback_type = mavlink_msg_voice_feedback_get_feedback_type(msg);
    voice_feedback->command_id = mavlink_msg_voice_feedback_get_command_id(msg);
    mavlink_msg_voice_feedback_get_message(msg, voice_feedback->message);
#else
        uint8_t len = msg->len < MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN? msg->len : MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN;
        memset(voice_feedback, 0, MAVLINK_MSG_ID_VOICE_FEEDBACK_LEN);
    memcpy(voice_feedback, _MAV_PAYLOAD(msg), len);
#endif
}
