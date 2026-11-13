#pragma once
// MESSAGE VOICE_STATUS PACKING

#include <stdint.h>

#define MAVLINK_MSG_ID_VOICE_STATUS 30001


typedef struct __mavlink_voice_status_t {
 uint32_t timestamp_ms; /*<  Timestamp in milliseconds since boot*/
 float cpu_usage; /*<  CPU usage percentage*/
 float memory_usage_mb; /*<  Memory usage in MB*/
 uint32_t commands_processed; /*<  Total commands processed*/
 uint32_t commands_failed; /*<  Failed commands count*/
 float last_latency_ms; /*<  Last command processing latency*/
 uint8_t vad_active; /*<  VAD active (1) or inactive (0)*/
 uint8_t asr_active; /*<  ASR active (1) or inactive (0)*/
 char current_model[32]; /*<  Current ASR model name*/
} mavlink_voice_status_t;

#define MAVLINK_MSG_ID_VOICE_STATUS_LEN 58
#define MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN 58
#define MAVLINK_MSG_ID_30001_LEN 58
#define MAVLINK_MSG_ID_30001_MIN_LEN 58

#define MAVLINK_MSG_ID_VOICE_STATUS_CRC 204
#define MAVLINK_MSG_ID_30001_CRC 204

#define MAVLINK_MSG_VOICE_STATUS_FIELD_CURRENT_MODEL_LEN 32

#if MAVLINK_COMMAND_24BIT
#define MAVLINK_MESSAGE_INFO_VOICE_STATUS { \
    30001, \
    "VOICE_STATUS", \
    9, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_status_t, timestamp_ms) }, \
         { "vad_active", NULL, MAVLINK_TYPE_UINT8_T, 0, 24, offsetof(mavlink_voice_status_t, vad_active) }, \
         { "asr_active", NULL, MAVLINK_TYPE_UINT8_T, 0, 25, offsetof(mavlink_voice_status_t, asr_active) }, \
         { "current_model", NULL, MAVLINK_TYPE_CHAR, 32, 26, offsetof(mavlink_voice_status_t, current_model) }, \
         { "cpu_usage", NULL, MAVLINK_TYPE_FLOAT, 0, 4, offsetof(mavlink_voice_status_t, cpu_usage) }, \
         { "memory_usage_mb", NULL, MAVLINK_TYPE_FLOAT, 0, 8, offsetof(mavlink_voice_status_t, memory_usage_mb) }, \
         { "commands_processed", NULL, MAVLINK_TYPE_UINT32_T, 0, 12, offsetof(mavlink_voice_status_t, commands_processed) }, \
         { "commands_failed", NULL, MAVLINK_TYPE_UINT32_T, 0, 16, offsetof(mavlink_voice_status_t, commands_failed) }, \
         { "last_latency_ms", NULL, MAVLINK_TYPE_FLOAT, 0, 20, offsetof(mavlink_voice_status_t, last_latency_ms) }, \
         } \
}
#else
#define MAVLINK_MESSAGE_INFO_VOICE_STATUS { \
    "VOICE_STATUS", \
    9, \
    {  { "timestamp_ms", NULL, MAVLINK_TYPE_UINT32_T, 0, 0, offsetof(mavlink_voice_status_t, timestamp_ms) }, \
         { "vad_active", NULL, MAVLINK_TYPE_UINT8_T, 0, 24, offsetof(mavlink_voice_status_t, vad_active) }, \
         { "asr_active", NULL, MAVLINK_TYPE_UINT8_T, 0, 25, offsetof(mavlink_voice_status_t, asr_active) }, \
         { "current_model", NULL, MAVLINK_TYPE_CHAR, 32, 26, offsetof(mavlink_voice_status_t, current_model) }, \
         { "cpu_usage", NULL, MAVLINK_TYPE_FLOAT, 0, 4, offsetof(mavlink_voice_status_t, cpu_usage) }, \
         { "memory_usage_mb", NULL, MAVLINK_TYPE_FLOAT, 0, 8, offsetof(mavlink_voice_status_t, memory_usage_mb) }, \
         { "commands_processed", NULL, MAVLINK_TYPE_UINT32_T, 0, 12, offsetof(mavlink_voice_status_t, commands_processed) }, \
         { "commands_failed", NULL, MAVLINK_TYPE_UINT32_T, 0, 16, offsetof(mavlink_voice_status_t, commands_failed) }, \
         { "last_latency_ms", NULL, MAVLINK_TYPE_FLOAT, 0, 20, offsetof(mavlink_voice_status_t, last_latency_ms) }, \
         } \
}
#endif

/**
 * @brief Pack a voice_status message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param vad_active  VAD active (1) or inactive (0)
 * @param asr_active  ASR active (1) or inactive (0)
 * @param current_model  Current ASR model name
 * @param cpu_usage  CPU usage percentage
 * @param memory_usage_mb  Memory usage in MB
 * @param commands_processed  Total commands processed
 * @param commands_failed  Failed commands count
 * @param last_latency_ms  Last command processing latency
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_status_pack(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg,
                               uint32_t timestamp_ms, uint8_t vad_active, uint8_t asr_active, const char *current_model, float cpu_usage, float memory_usage_mb, uint32_t commands_processed, uint32_t commands_failed, float last_latency_ms)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_STATUS_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, cpu_usage);
    _mav_put_float(buf, 8, memory_usage_mb);
    _mav_put_uint32_t(buf, 12, commands_processed);
    _mav_put_uint32_t(buf, 16, commands_failed);
    _mav_put_float(buf, 20, last_latency_ms);
    _mav_put_uint8_t(buf, 24, vad_active);
    _mav_put_uint8_t(buf, 25, asr_active);
    _mav_put_char_array(buf, 26, current_model, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_STATUS_LEN);
#else
    mavlink_voice_status_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.cpu_usage = cpu_usage;
    packet.memory_usage_mb = memory_usage_mb;
    packet.commands_processed = commands_processed;
    packet.commands_failed = commands_failed;
    packet.last_latency_ms = last_latency_ms;
    packet.vad_active = vad_active;
    packet.asr_active = asr_active;
    mav_array_memcpy(packet.current_model, current_model, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_STATUS_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_STATUS;
    return mavlink_finalize_message(msg, system_id, component_id, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN, MAVLINK_MSG_ID_VOICE_STATUS_CRC);
}

/**
 * @brief Pack a voice_status message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param vad_active  VAD active (1) or inactive (0)
 * @param asr_active  ASR active (1) or inactive (0)
 * @param current_model  Current ASR model name
 * @param cpu_usage  CPU usage percentage
 * @param memory_usage_mb  Memory usage in MB
 * @param commands_processed  Total commands processed
 * @param commands_failed  Failed commands count
 * @param last_latency_ms  Last command processing latency
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_status_pack_status(uint8_t system_id, uint8_t component_id, mavlink_status_t *_status, mavlink_message_t* msg,
                               uint32_t timestamp_ms, uint8_t vad_active, uint8_t asr_active, const char *current_model, float cpu_usage, float memory_usage_mb, uint32_t commands_processed, uint32_t commands_failed, float last_latency_ms)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_STATUS_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, cpu_usage);
    _mav_put_float(buf, 8, memory_usage_mb);
    _mav_put_uint32_t(buf, 12, commands_processed);
    _mav_put_uint32_t(buf, 16, commands_failed);
    _mav_put_float(buf, 20, last_latency_ms);
    _mav_put_uint8_t(buf, 24, vad_active);
    _mav_put_uint8_t(buf, 25, asr_active);
    _mav_put_char_array(buf, 26, current_model, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_STATUS_LEN);
#else
    mavlink_voice_status_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.cpu_usage = cpu_usage;
    packet.memory_usage_mb = memory_usage_mb;
    packet.commands_processed = commands_processed;
    packet.commands_failed = commands_failed;
    packet.last_latency_ms = last_latency_ms;
    packet.vad_active = vad_active;
    packet.asr_active = asr_active;
    mav_array_memcpy(packet.current_model, current_model, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_STATUS_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_STATUS;
#if MAVLINK_CRC_EXTRA
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN, MAVLINK_MSG_ID_VOICE_STATUS_CRC);
#else
    return mavlink_finalize_message_buffer(msg, system_id, component_id, _status, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN);
#endif
}

/**
 * @brief Pack a voice_status message on a channel
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param vad_active  VAD active (1) or inactive (0)
 * @param asr_active  ASR active (1) or inactive (0)
 * @param current_model  Current ASR model name
 * @param cpu_usage  CPU usage percentage
 * @param memory_usage_mb  Memory usage in MB
 * @param commands_processed  Total commands processed
 * @param commands_failed  Failed commands count
 * @param last_latency_ms  Last command processing latency
 * @return length of the message in bytes (excluding serial stream start sign)
 */
static inline uint16_t mavlink_msg_voice_status_pack_chan(uint8_t system_id, uint8_t component_id, uint8_t chan,
                               mavlink_message_t* msg,
                                   uint32_t timestamp_ms,uint8_t vad_active,uint8_t asr_active,const char *current_model,float cpu_usage,float memory_usage_mb,uint32_t commands_processed,uint32_t commands_failed,float last_latency_ms)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_STATUS_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, cpu_usage);
    _mav_put_float(buf, 8, memory_usage_mb);
    _mav_put_uint32_t(buf, 12, commands_processed);
    _mav_put_uint32_t(buf, 16, commands_failed);
    _mav_put_float(buf, 20, last_latency_ms);
    _mav_put_uint8_t(buf, 24, vad_active);
    _mav_put_uint8_t(buf, 25, asr_active);
    _mav_put_char_array(buf, 26, current_model, 32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), buf, MAVLINK_MSG_ID_VOICE_STATUS_LEN);
#else
    mavlink_voice_status_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.cpu_usage = cpu_usage;
    packet.memory_usage_mb = memory_usage_mb;
    packet.commands_processed = commands_processed;
    packet.commands_failed = commands_failed;
    packet.last_latency_ms = last_latency_ms;
    packet.vad_active = vad_active;
    packet.asr_active = asr_active;
    mav_array_memcpy(packet.current_model, current_model, sizeof(char)*32);
        memcpy(_MAV_PAYLOAD_NON_CONST(msg), &packet, MAVLINK_MSG_ID_VOICE_STATUS_LEN);
#endif

    msg->msgid = MAVLINK_MSG_ID_VOICE_STATUS;
    return mavlink_finalize_message_chan(msg, system_id, component_id, chan, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN, MAVLINK_MSG_ID_VOICE_STATUS_CRC);
}

/**
 * @brief Encode a voice_status struct
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 * @param voice_status C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_status_encode(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg, const mavlink_voice_status_t* voice_status)
{
    return mavlink_msg_voice_status_pack(system_id, component_id, msg, voice_status->timestamp_ms, voice_status->vad_active, voice_status->asr_active, voice_status->current_model, voice_status->cpu_usage, voice_status->memory_usage_mb, voice_status->commands_processed, voice_status->commands_failed, voice_status->last_latency_ms);
}

/**
 * @brief Encode a voice_status struct on a channel
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param chan The MAVLink channel this message will be sent over
 * @param msg The MAVLink message to compress the data into
 * @param voice_status C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_status_encode_chan(uint8_t system_id, uint8_t component_id, uint8_t chan, mavlink_message_t* msg, const mavlink_voice_status_t* voice_status)
{
    return mavlink_msg_voice_status_pack_chan(system_id, component_id, chan, msg, voice_status->timestamp_ms, voice_status->vad_active, voice_status->asr_active, voice_status->current_model, voice_status->cpu_usage, voice_status->memory_usage_mb, voice_status->commands_processed, voice_status->commands_failed, voice_status->last_latency_ms);
}

/**
 * @brief Encode a voice_status struct with provided status structure
 *
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param status MAVLink status structure
 * @param msg The MAVLink message to compress the data into
 * @param voice_status C-struct to read the message contents from
 */
static inline uint16_t mavlink_msg_voice_status_encode_status(uint8_t system_id, uint8_t component_id, mavlink_status_t* _status, mavlink_message_t* msg, const mavlink_voice_status_t* voice_status)
{
    return mavlink_msg_voice_status_pack_status(system_id, component_id, _status, msg,  voice_status->timestamp_ms, voice_status->vad_active, voice_status->asr_active, voice_status->current_model, voice_status->cpu_usage, voice_status->memory_usage_mb, voice_status->commands_processed, voice_status->commands_failed, voice_status->last_latency_ms);
}

/**
 * @brief Send a voice_status message
 * @param chan MAVLink channel to send the message
 *
 * @param timestamp_ms  Timestamp in milliseconds since boot
 * @param vad_active  VAD active (1) or inactive (0)
 * @param asr_active  ASR active (1) or inactive (0)
 * @param current_model  Current ASR model name
 * @param cpu_usage  CPU usage percentage
 * @param memory_usage_mb  Memory usage in MB
 * @param commands_processed  Total commands processed
 * @param commands_failed  Failed commands count
 * @param last_latency_ms  Last command processing latency
 */
#ifdef MAVLINK_USE_CONVENIENCE_FUNCTIONS

static inline void mavlink_msg_voice_status_send(mavlink_channel_t chan, uint32_t timestamp_ms, uint8_t vad_active, uint8_t asr_active, const char *current_model, float cpu_usage, float memory_usage_mb, uint32_t commands_processed, uint32_t commands_failed, float last_latency_ms)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char buf[MAVLINK_MSG_ID_VOICE_STATUS_LEN];
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, cpu_usage);
    _mav_put_float(buf, 8, memory_usage_mb);
    _mav_put_uint32_t(buf, 12, commands_processed);
    _mav_put_uint32_t(buf, 16, commands_failed);
    _mav_put_float(buf, 20, last_latency_ms);
    _mav_put_uint8_t(buf, 24, vad_active);
    _mav_put_uint8_t(buf, 25, asr_active);
    _mav_put_char_array(buf, 26, current_model, 32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_STATUS, buf, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN, MAVLINK_MSG_ID_VOICE_STATUS_CRC);
#else
    mavlink_voice_status_t packet;
    packet.timestamp_ms = timestamp_ms;
    packet.cpu_usage = cpu_usage;
    packet.memory_usage_mb = memory_usage_mb;
    packet.commands_processed = commands_processed;
    packet.commands_failed = commands_failed;
    packet.last_latency_ms = last_latency_ms;
    packet.vad_active = vad_active;
    packet.asr_active = asr_active;
    mav_array_memcpy(packet.current_model, current_model, sizeof(char)*32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_STATUS, (const char *)&packet, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN, MAVLINK_MSG_ID_VOICE_STATUS_CRC);
#endif
}

/**
 * @brief Send a voice_status message
 * @param chan MAVLink channel to send the message
 * @param struct The MAVLink struct to serialize
 */
static inline void mavlink_msg_voice_status_send_struct(mavlink_channel_t chan, const mavlink_voice_status_t* voice_status)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    mavlink_msg_voice_status_send(chan, voice_status->timestamp_ms, voice_status->vad_active, voice_status->asr_active, voice_status->current_model, voice_status->cpu_usage, voice_status->memory_usage_mb, voice_status->commands_processed, voice_status->commands_failed, voice_status->last_latency_ms);
#else
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_STATUS, (const char *)voice_status, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN, MAVLINK_MSG_ID_VOICE_STATUS_CRC);
#endif
}

#if MAVLINK_MSG_ID_VOICE_STATUS_LEN <= MAVLINK_MAX_PAYLOAD_LEN
/*
  This variant of _send() can be used to save stack space by reusing
  memory from the receive buffer.  The caller provides a
  mavlink_message_t which is the size of a full mavlink message. This
  is usually the receive buffer for the channel, and allows a reply to an
  incoming message with minimum stack space usage.
 */
static inline void mavlink_msg_voice_status_send_buf(mavlink_message_t *msgbuf, mavlink_channel_t chan,  uint32_t timestamp_ms, uint8_t vad_active, uint8_t asr_active, const char *current_model, float cpu_usage, float memory_usage_mb, uint32_t commands_processed, uint32_t commands_failed, float last_latency_ms)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    char *buf = (char *)msgbuf;
    _mav_put_uint32_t(buf, 0, timestamp_ms);
    _mav_put_float(buf, 4, cpu_usage);
    _mav_put_float(buf, 8, memory_usage_mb);
    _mav_put_uint32_t(buf, 12, commands_processed);
    _mav_put_uint32_t(buf, 16, commands_failed);
    _mav_put_float(buf, 20, last_latency_ms);
    _mav_put_uint8_t(buf, 24, vad_active);
    _mav_put_uint8_t(buf, 25, asr_active);
    _mav_put_char_array(buf, 26, current_model, 32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_STATUS, buf, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN, MAVLINK_MSG_ID_VOICE_STATUS_CRC);
#else
    mavlink_voice_status_t *packet = (mavlink_voice_status_t *)msgbuf;
    packet->timestamp_ms = timestamp_ms;
    packet->cpu_usage = cpu_usage;
    packet->memory_usage_mb = memory_usage_mb;
    packet->commands_processed = commands_processed;
    packet->commands_failed = commands_failed;
    packet->last_latency_ms = last_latency_ms;
    packet->vad_active = vad_active;
    packet->asr_active = asr_active;
    mav_array_memcpy(packet->current_model, current_model, sizeof(char)*32);
    _mav_finalize_message_chan_send(chan, MAVLINK_MSG_ID_VOICE_STATUS, (const char *)packet, MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN, MAVLINK_MSG_ID_VOICE_STATUS_LEN, MAVLINK_MSG_ID_VOICE_STATUS_CRC);
#endif
}
#endif

#endif

// MESSAGE VOICE_STATUS UNPACKING


/**
 * @brief Get field timestamp_ms from voice_status message
 *
 * @return  Timestamp in milliseconds since boot
 */
static inline uint32_t mavlink_msg_voice_status_get_timestamp_ms(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint32_t(msg,  0);
}

/**
 * @brief Get field vad_active from voice_status message
 *
 * @return  VAD active (1) or inactive (0)
 */
static inline uint8_t mavlink_msg_voice_status_get_vad_active(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  24);
}

/**
 * @brief Get field asr_active from voice_status message
 *
 * @return  ASR active (1) or inactive (0)
 */
static inline uint8_t mavlink_msg_voice_status_get_asr_active(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint8_t(msg,  25);
}

/**
 * @brief Get field current_model from voice_status message
 *
 * @return  Current ASR model name
 */
static inline uint16_t mavlink_msg_voice_status_get_current_model(const mavlink_message_t* msg, char *current_model)
{
    return _MAV_RETURN_char_array(msg, current_model, 32,  26);
}

/**
 * @brief Get field cpu_usage from voice_status message
 *
 * @return  CPU usage percentage
 */
static inline float mavlink_msg_voice_status_get_cpu_usage(const mavlink_message_t* msg)
{
    return _MAV_RETURN_float(msg,  4);
}

/**
 * @brief Get field memory_usage_mb from voice_status message
 *
 * @return  Memory usage in MB
 */
static inline float mavlink_msg_voice_status_get_memory_usage_mb(const mavlink_message_t* msg)
{
    return _MAV_RETURN_float(msg,  8);
}

/**
 * @brief Get field commands_processed from voice_status message
 *
 * @return  Total commands processed
 */
static inline uint32_t mavlink_msg_voice_status_get_commands_processed(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint32_t(msg,  12);
}

/**
 * @brief Get field commands_failed from voice_status message
 *
 * @return  Failed commands count
 */
static inline uint32_t mavlink_msg_voice_status_get_commands_failed(const mavlink_message_t* msg)
{
    return _MAV_RETURN_uint32_t(msg,  16);
}

/**
 * @brief Get field last_latency_ms from voice_status message
 *
 * @return  Last command processing latency
 */
static inline float mavlink_msg_voice_status_get_last_latency_ms(const mavlink_message_t* msg)
{
    return _MAV_RETURN_float(msg,  20);
}

/**
 * @brief Decode a voice_status message into a struct
 *
 * @param msg The message to decode
 * @param voice_status C-struct to decode the message contents into
 */
static inline void mavlink_msg_voice_status_decode(const mavlink_message_t* msg, mavlink_voice_status_t* voice_status)
{
#if MAVLINK_NEED_BYTE_SWAP || !MAVLINK_ALIGNED_FIELDS
    voice_status->timestamp_ms = mavlink_msg_voice_status_get_timestamp_ms(msg);
    voice_status->cpu_usage = mavlink_msg_voice_status_get_cpu_usage(msg);
    voice_status->memory_usage_mb = mavlink_msg_voice_status_get_memory_usage_mb(msg);
    voice_status->commands_processed = mavlink_msg_voice_status_get_commands_processed(msg);
    voice_status->commands_failed = mavlink_msg_voice_status_get_commands_failed(msg);
    voice_status->last_latency_ms = mavlink_msg_voice_status_get_last_latency_ms(msg);
    voice_status->vad_active = mavlink_msg_voice_status_get_vad_active(msg);
    voice_status->asr_active = mavlink_msg_voice_status_get_asr_active(msg);
    mavlink_msg_voice_status_get_current_model(msg, voice_status->current_model);
#else
        uint8_t len = msg->len < MAVLINK_MSG_ID_VOICE_STATUS_LEN? msg->len : MAVLINK_MSG_ID_VOICE_STATUS_LEN;
        memset(voice_status, 0, MAVLINK_MSG_ID_VOICE_STATUS_LEN);
    memcpy(voice_status, _MAV_PAYLOAD(msg), len);
#endif
}
