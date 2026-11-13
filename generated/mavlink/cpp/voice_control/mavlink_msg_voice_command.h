#pragma once
// MESSAGE VOICE_COMMAND PACKING

#include <stdint.h>

#define MAVLINK_MSG_ID_VOICE_COMMAND 30000


typedef struct __mavlink_voice_command_t {
 uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot*/
 float params[10]; /*<  Action parameters (lat, lon, alt, speed, heading, etc.)*/
 float confidence; /*<  ASR confidence 0.0-1.0*/
 char command_text[128]; /*<  Raw recognized text*/
 char parsed_action[32]; /*<  Parsed action: TAKEOFF, LAND, GOTO, RTL, HOVER, SET_MODE, ARM, DISARM*/
 uint8_t param_count; /*<  Number of valid parameters*/
 uint8_t is_final; /*<  Final result (1) or partial (0)*/
 uint8_t command_id; /*<  Unique command sequence ID*/
} mavlink_voice_command_t;

#define MAVLINK_MSG_ID_VOICE_COMMAND_LEN 211
#define MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN 211
#define MAVLINK_MSG_ID_30000_LEN 211
#define MAVLINK_MSG_ID_30000_MIN_LEN 211

#define MAVLINK_MSG_ID_VOICE_COMMAND_CRC 147
#define MAVLINK_MSG_ID_30000_CRC 147

#define MAVLINK_MSG_VOICE_COMMAND_FIELD_PARAMS_LEN 10
#define MAVLINK_MSG_VOICE_COMMAND_FIELD_COMMAND_TEXT_LEN 128
#define MAVLINK_MSG_VOICE_COMMAND_FIELD_PARSED_ACTION_LEN 32

#if MAVLINK_COMMAND_24BIT
#define MAVLINK_MESSAGE_INFO_VOICE_COMMAND { \
    30000, \
    "VOICE_COMMAND", \
    8, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_command_t, timestamp_ms) }, \
         { "command_text", NULL, MAVLINK_TYPE_CHAR, 128, 48, offsetof(mavlink_voice_command_t, command_text) }, \
         { "parsed_action", NULL, MAVLINK_TYPE_CHAR, 32, 176, offsetof(mavlink_voice_command_t, parsed_action) }, \
         { "params", NULL, MAVLINK_TYPE_FLOAT, 10, 4, offsetof(mavlink_voice_command_t, params) }, \
         { "param_count", NULL, MAVLINK_TYPE_UINT8_T, 0, 208, offsetof(mavlink_voice_command_t, param_count) }, \
         { "confidence", NULL, MAVLINK_TYPE_FLOAT, 0, 44, offsetof(mavlink_voice_command_t, confidence) }, \
         { "is_final", NULL, MAVLINK_TYPE_UINT8_T, 0, 209, offsetof(mavlink_voice_command_t, is_final) }, \
         { "command_id", NULL, MAVLINK_TYPE_UINT8_T, 0, 210, offsetof(mavlink_voice_command_t, command_id) }, \
         } \
}
#else
#define MAVLINK_MESSAGE_INFO_VOICE_COMMAND { \
    "VOICE_COMMAND", \
    8, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_command_t, timestamp_ms) }, \
         { "command_text", NULL, MAVLINK_TYPE_CHAR, 128, 48, offsetof(mavlink_voice_command_t, command_text) }, \
         { "parsed_action", NULL, MAVLINK_TYPE_CHAR, 32, 176, offsetof(mavlink_voice_command_t, parsed_action) }, \
         { "params", NULL, MAVLINK_TYPE_FLOAT, 10, 4, offsetof(mavlink_voice_command_t, params) }, \
         { "param_count", NULL, MAVLINK_TYPE_UINT8_T, 0, 208, offsetof(mavlink_voice_command_t, param_count) }, \
         { "confidence", NULL, MAVLINK_TYPE_FLOAT, 0, 44, offsetof(mavlink_voice_command_t, confidence) }, \
         { "is_final", NULL, MAVLINK_TYPE_UINT8_T, 0, 209, offsetof(mavlink_voice_command_t, is_final) }, \
         { "command_id", NULL, MAVLINK_TYPE_UINT8_T, 0, 210, offsetof(mavlink_voice_command_t, command_id) }, \
         } \
}
#endif

/**
 * @brief Pack a voice_command message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param command_text  Raw recognized text
 * @param parsed_action  Parsed action: TAKEOFF, LAND, GOTO, RTL, HOVER, SET_MODE, ARM, DISARM
 * @param params  Action parameters (lat, lon, alt, speed, heading, etc.)
 * @param param_count  Number of valid parameters
 * @param confidence  ASR confidence 0.0-1.0
 * @param is_final  Final result (1) or partial (0)
 * @param command_id  Unique command sequence ID
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_command_pack(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg,
                               uint32_t timestamp_ms, const char *command_text, const char *parsed_action, const float *params, uint8_t param_count, float confidence, uint8_t is_final, uint8_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_COMMAND_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 44, confidence);
    _mav_put_uint8_t(buf, 208, param_count);
    _mav_put_uint8_t(buf, 209, is_final);
    _mav_put_uint8_t(buf, 210, command_id);
    _mav_put_float_array(buf, 4, params, 10);
    _mav_put_char_array(buf, 48, command_text, 128);
    _mav_put_char_array(buf, 176, parsed_action, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_COMMAND_LEN);
#else
    mavlink_voice_command_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.confidence = confidence;
    packet.param_count = param_count;
    packet.is_final = is_final;
    packet.command_id = command_id;
    mav_array_memcpy(packet.params, params, sizeof(float)*10);
    mav_array_memcpy(packet.command_text, command_text, sizeof(char)*128);
    mav_array_memcpy(packet.parsed_action, parsed_action, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_COMMAND_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_COMMAND;
    return mavlink_finalize_message(msg, system_id, component_id, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_CRC);
}

/**
 * @brief Pack a voice_command message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param command_text  Raw recognized text
 * @param parsed_action  Parsed action: TAKEOFF, LAND, GOTO, RTL, HOVER, SET_MODE, ARM, DISARM
 * @param params  Action parameters (lat, lon, alt, speed, heading, etc.)
 * @param param_count  Number of valid parameters
 * @param confidence  ASR confidence 0.0-1.0
 * @param is_final  Final result (1) or partial (0)
 * @param command_id  Unique command sequence ID
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_command_pack_status(uint8_t system_id, uint8_t component_id, mavlink_status_t *_status, mavlink_message_t* msg,
                               uint32_t timestamp_ms, const char *command_text, const char *parsed_action, const float *params, uint8_t param_count, float confidence, uint8_t is_final, uint8_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_COMMAND_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 44, confidence);
    _mav_put_uint8_t(buf, 208, param_count);
    _mav_put_uint8_t(buf, 209, is_final);
    _mav_put_uint8_t(buf, 210, command_id);
    _mav_put_float_array(buf, 4, params, 10);
    _mav_put_char_array(buf, 48, command_text, 128);
    _mav_put_char_array(buf, 176, parsed_action, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_COMMAND_LEN);
#else
    mavlink_voice_command_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.confidence = confidence;
    packet.param_count = param_count;
    packet.is_final = is_final;
    packet.command_id = command_id;
    mav_array_memcpy(packet.params, params, sizeof(float)*10);
    mav_array_memcpy(packet.command_text, command_text, sizeof(char)*128);
    mav_array_memcpy(packet.parsed_action, parsed_action, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_COMMAND_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_COMMAND;
#if MAVLINK_CRC_EXTRA
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_CRC);
#else
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN);
#endif
}

/**
 * @brief Pack a voice_command message on a channel
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param command_text  Raw recognized text
 * @param parsed_action  Parsed action: TAKEOFF, LAND, GOTO, RTL, HOVER, SET_MODE, ARM, DISARM
 * @param params  Action parameters (lat, lon, alt, speed, heading, etc.)
 * @param param_count  Number of valid parameters
 * @param confidence  ASR confidence 0.0-1.0
 * @param is_final  Final result (1) or partial (0)
 * @param command_id  Unique command sequence ID
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_command_pack_chan(uint8_t system_id, uint8_t component_id, uint8_t chan,
                               mavlink_message_t* msg,
                                   uint32_t timestamp_ms,const char *command_text,const char *parsed_action,const float *params,uint8_t param_count,float confidence,uint8_t is_final,uint8_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_COMMAND_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 44, confidence);
    _mav_put_uint8_t(buf, 208, param_count);
    _mav_put_uint8_t(buf, 209, is_final);
    _mav_put_uint8_t(buf, 210, command_id);
    _mav_put_float_array(buf, 4, params, 10);
    _mav_put_char_array(buf, 48, command_text, 128);
    _mav_put_char_array(buf, 176, parsed_action, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_COMMAND_LEN);
#else
    mavlink_voice_command_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.confidence = confidence;
    packet.param_count = param_count;
    packet.is_final = is_final;
    packet.command_id = command_id;
    mav_array_memcpy(packet.params, params, sizeof(float)*10);
    mav_array_memcpy(packet.command_text, command_text, sizeof(char)*128);
    mav_array_memcpy(packet.parsed_action, parsed_action, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_COMMAND_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_COMMAND;
    return mavlink_finalize_message_chan(msg, system_id, component_id, chan, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_CRC);
}

/**
 * @brief Encode a voice_command struct
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 * @param voice_command C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_command_encode(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg, const mavlink_voice_command_t* voice_command)
{
    return mavlink_msg_voice_command_pack(system_id, component_id, msg, voice_command->timestamp_ms, voice_command->command_text, voice_command->parsed_action, voice_command->params, voice_command->param_count, voice_command->confidence, voice_command->is_final, voice_command->command_id);
}

/**
 * @brief Encode a voice_command struct on a channel
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param voice_command C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_command_encode_chan(uint8_t system_id, uint8_t component_id, uint8_t chan, mavlink_message_t* msg, const mavlink_voice_command_t* voice_command)
{
    return mavlink_msg_voice_command_pack_chan(system_id, component_id, chan, msg, voice_command->timestamp_ms, voice_command->command_text, voice_command->parsed_action, voice_command->params, voice_command->param_count, voice_command->confidence, voice_command->is_final, voice_command->command_id);
}

/**
 * @brief Encode a voice_command struct with provided status structure
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 * @param voice_command C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_command_encode_status(uint8_t system_id, uint8_t component_id, mavlink_status_t* _status, mavlink_message_t* msg, const mavlink_voice_command_t* voice_command)
{
    return mavlink_msg_voice_command_pack_status(system_id, component_id, _status, msg,  voice_command->timestamp_ms, voice_command->command_text, voice_command->parsed_action, voice_command->params, voice_command->param_count, voice_command->confidence, voice_command->is_final, voice_command->command_id);
}

/**
 * @brief Send a voice_command message
 * @param chan MAVLink channel to send the message
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param command_text  Raw recognized text
 * @param parsed_action  Parsed action: TAKEOFF, LAND, GOTO, RTL, HOVER, SET_MODE, ARM, DISARM
 * @param params  Action parameters (lat, lon, alt, speed, heading, etc.)
 * @param param_count  Number of valid parameters
 * @param confidence  ASR confidence 0.0-1.0
 * @param is_final  Final result (1) or partial (0)
 * @param command_id  Unique command sequence ID
 */
#ifdef MAVLINK_USE_CONVENIENCE_FUNCTIONS

static inline void mavlink_msg_voice_command_send(mavlink_channel_t chan, uint32_t timestamp_ms, const char *command_text, const char *parsed_action, const float *params, uint8_t param_count, float confidence, uint8_t is_final, uint8_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_COMMAND_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 44, confidence);
    _mav_put_uint8_t(buf, 208, param_count);
    _mav_put_uint8_t(buf, 209, is_final);
    _mav_put_uint8_t(buf, 210, command_id);
    _mav_put_float_array(buf, 4, params, 10);
    _mav_put_char_array(buf, 48, command_text, 128);
    _mav_put_char_array(buf, 176, parsed_action, 32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_COMMAND, buf, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_CRC);
#else
    mavlink_voice_command_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.confidence = confidence;
    packet.param_count = param_count;
    packet.is_final = is_final;
    packet.command_id = command_id;
    mav_array_memcpy(packet.params, params, sizeof(float)*10);
    mav_array_memcpy(packet.command_text, command_text, sizeof(char)*128);
    mav_array_memcpy(packet.parsed_action, parsed_action, sizeof(char)*32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_COMMAND, (const char *)&packet, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_CRC);
#endif
}

/**
 * @brief Send a voice_command message
 * @param chan MAVLink channel to send the message
 * @param struct The MAVLink struct to serialize
 */
static inline void mavlink_msg_voice_command_send_struct(mavlink_channel_t chan, const mavlink_voice_command_t* voice_command)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    mavlink_msg_voice_command_send(chan, voice_command->timestamp_ms, voice_command->command_text, voice_command->parsed_action, voice_command->params, voice_command->param_count, voice_command->confidence, voice_command->is_final, voice_command->command_id);
#else
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_COMMAND, (const char *)voice_command, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_CRC);
#endif
}

#if MAVLINK_MSG_ID_VOICE_COMMAND_LEN <= MAVLINK_MAX_PAYLOAD_LEN
/*
  This variant of _send() can be used to save stack space by reusing
  memory from the receive buffer.  The caller provides a
  mavlink_message_t which is the size of a full mavlink message. This
  is usually the receive buffer for the channel, and allows a reply to an
  incoming message with minimum stack space usage.
 */
static inline void mavlink_msg_voice_command_send_buf(mavlink_message_t *msgbuf, mavlink_channel_t chan,  uint32_t timestamp_ms, const char *command_text, const char *parsed_action, const float *params, uint8_t param_count, float confidence, uint8_t is_final, uint8_t command_id)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char *buf = (char *)msgbuf;
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 44, confidence);
    _mav_put_uint8_t(buf, 208, param_count);
    _mav_put_uint8_t(buf, 209, is_final);
    _mav_put_uint8_t(buf, 210, command_id);
    _mav_put_float_array(buf, 4, params, 10);
    _mav_put_char_array(buf, 48, command_text, 128);
    _mav_put_char_array(buf, 176, parsed_action, 32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_COMMAND, buf, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_CRC);
#else
    mavlink_voice_command_t *packet = (mavlink_voice_command_t *)msgbuf;
    packet->timestamp_ms = timestamp_ms;
    packet->confidence = confidence;
    packet->param_count = param_count;
    packet->is_final = is_final;
    packet->command_id = command_id;
    mav_array_memcpy(packet->params, params, sizeof(float)*10);
    mav_array_memcpy(packet->command_text, command_text, sizeof(char)*128);
    mav_array_memcpy(packet->parsed_action, parsed_action, sizeof(char)*32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_COMMAND, (const char *)packet, MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_LEN, MAVLINK_MSG_ID_VOICE_COMMAND_CRC);
#endif
}
#endif

#endif

// MESSAGE VOICE_COMMAND UNPACKING


/**
 * @brief Get field timestamp_ms from voice_command message
 *
 * @return  Timestamp in milliseconds since boot
 */
static inline uint32_t mavlink_msg_voice_command_get_timestamp_ms(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint32_t(msg,  0);
}

/**
 * @brief Get field command_text from voice_command message
 *
 * @return  Raw recognized text
 */
static inline uint16_t mavlink_msg_voice_command_get_command_text(const mavlink_message_t* msg, char *command_text)
{
    return _MAV_RETURN_char_array(msg, command_text, 128,  48);
}

/**
 * @brief Get field parsed_action from voice_command message
 *
 * @return  Parsed action: TAKEOFF, LAND, GOTO, RTL, HOVER, SET_MODE, ARM, DISARM
 */
static inline uint16_t mavlink_msg_voice_command_get_parsed_action(const mavlink_message_t* msg, char *parsed_action)
{
    return _MAV_RETURN_char_array(msg, parsed_action, 32,  176);
}

/**
 * @brief Get field params from voice_command message
 *
 * @return  Action parameters (lat, lon, alt, speed, heading, etc.)
 */
static inline uint16_t mavlink_msg_voice_command_get_params(const mavlink_message_t* msg, float *params)
{
    return _MAV_RETURN_float_array(msg, params, 10,  4);
}

/**
 * @brief Get field param_count from voice_command message
 *
 * @return  Number of valid parameters
 */
static inline uint8_t mavlink_msg_voice_command_get_param_count(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  208);
}

/**
 * @brief Get field confidence from voice_command message
 *
 * @return  ASR confidence 0.0-1.0
 */
static inline float mavlink_msg_voice_command_get_confidence(const mavlink_message_t* msg)
{
    return _MAV_RETURN_float(msg,  44);
}

/**
 * @brief Get field is_final from voice_command message
 *
 * @return  Final result (1) or partial (0)
 */
static inline uint8_t mavlink_msg_voice_command_get_is_final(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  209);
}

/**
 * @brief Get field command_id from voice_command message
 *
 * @return  Unique command sequence ID
 */
static inline uint8_t mavlink_msg_voice_command_get_command_id(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  210);
}

/**
 * @brief Decode a voice_command message into a struct
 *
 * @param msg The message to decode
 * @param voice_command C-struct to decode the message contents into
 */
static inline void mavlink_msg_voice_command_decode(const mavlink_message_t* msg, mavlink_voice_command_t* voice_command)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    voice_command->timestamp_ms = mavlink_msg_voice_command_get_timestamp_ms(msg);
    mavlink_msg_voice_command_get_params(msg, voice_command->params);
    voice_command->confidence = mavlink_msg_voice_command_get_confidence(msg);
    mavlink_msg_voice_command_get_command_text(msg, voice_command->command_text);
    mavlink_msg_voice_command_get_parsed_action(msg, voice_command->parsed_action);
    voice_command->param_count = mavlink_msg_voice_command_get_param_count(msg);
    voice_command->is_final = mavlink_msg_voice_command_get_is_final(msg);
    voice_command->command_id = mavlink_msg_voice_command_get_command_id(msg);
#else
        uint8_t len = msg->len < MAVLINK_MSG_ID_VOICE_COMMAND_LEN? msg->len : MAVLINK_MSG_ID_VOICE_COMMAND_LEN;
        memset(voice_command, 0, MAVLINK_MSG_ID_VOICE_COMMAND_LEN);
    memcpy(voice_command, _MAV_PAYLOAD(msg), len);
#endif
}
