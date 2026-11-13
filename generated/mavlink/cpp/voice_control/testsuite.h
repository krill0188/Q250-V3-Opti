/** @file
 *    @brief MAVLink comm protocol testsuite generated from voice_control.xml
 *    @see https://mavlink.io/en/
 */
#pragma once
#ifndef VOICE_CONTROL_TESTSUITE_H
#define VOICE_CONTROL_TESTSUITE_H

#ifdef __cplusplus
extern "C" {
#endif

#ifndef MAVLINK_TEST_ALL
#define MAVLINK_TEST_ALL
static void mavlink_test_common(uint8_t, uint8_t, mavlink_message_t *last_msg);
static void mavlink_test_ardupilotmega(uint8_t, uint8_t, mavlink_message_t *last_msg);
static void mavlink_test_voice_control(uint8_t, uint8_t, mavlink_message_t *last_msg);

static void mavlink_test_all(uint8_t system_id, uint8_t component_id, mavlink_message_t *last_msg)
{
    mavlink_test_common(system_id, component_id, last_msg);
    mavlink_test_ardupilotmega(system_id, component_id, last_msg);
    mavlink_test_voice_control(system_id, component_id, last_msg);
}
#endif

#include "../common/testsuite.h"
#include "../ardupilotmega/testsuite.h"


static void mavlink_test_voice_command(uint8_t system_id, uint8_t component_id, mavlink_message_t *last_msg)
{
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
    mavlink_status_t *status = mavlink_get_channel_status(MAVLINK_COMM_0);
        if ((status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) && MAVLINK_MSG_ID_VOICE_COMMAND >= 256) {
            return;
        }
#endif
    mavlink_message_t msg;
        uint8_t buffer[MAVLINK_MAX_PACKET_LEN];
        uint16_t i;
    mavlink_voice_command_t packet_in = {
        963497464,{ 45.0, 46.0, 47.0, 48.0, 49.0, 50.0, 51.0, 52.0, 53.0, 54.0 },325.0,"WXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRS","UVWXYZABCDEFGHIJKLMNOPQRSTUVWXY",117,184,251
    };
    mavlink_voice_command_t packet1, packet2;
        memset(&packet1, 0, sizeof(packet1));
        packet1.timestamp_ms = packet_in.timestamp_ms;
        packet1.confidence = packet_in.confidence;
        packet1.param_count = packet_in.param_count;
        packet1.is_final = packet_in.is_final;
        packet1.command_id = packet_in.command_id;
        
        mav_array_memcpy(packet1.params, packet_in.params, sizeof(float)*10);
        mav_array_memcpy(packet1.command_text, packet_in.command_text, sizeof(char)*128);
        mav_array_memcpy(packet1.parsed_action, packet_in.parsed_action, sizeof(char)*32);
        
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
        if (status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) {
           // cope with extensions
           memset(MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN + (char *)&packet1, 0, sizeof(packet1)-MAVLINK_MSG_ID_VOICE_COMMAND_MIN_LEN);
        }
#endif
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_command_encode(system_id, component_id, &msg, &packet1);
    mavlink_msg_voice_command_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_command_pack(system_id, component_id, &msg , packet1.timestamp_ms , packet1.command_text , packet1.parsed_action , packet1.params , packet1.param_count , packet1.confidence , packet1.is_final , packet1.command_id );
    mavlink_msg_voice_command_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_command_pack_chan(system_id, component_id, MAVLINK_COMM_0, &msg , packet1.timestamp_ms , packet1.command_text , packet1.parsed_action , packet1.params , packet1.param_count , packet1.confidence , packet1.is_final , packet1.command_id );
    mavlink_msg_voice_command_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
        mavlink_msg_to_send_buffer(buffer, &msg);
        for (i=0; i<mavlink_msg_get_send_buffer_length(&msg); i++) {
            comm_send_ch(MAVLINK_COMM_0, buffer[i]);
        }
    mavlink_msg_voice_command_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);
        
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_command_send(MAVLINK_COMM_1 , packet1.timestamp_ms , packet1.command_text , packet1.parsed_action , packet1.params , packet1.param_count , packet1.confidence , packet1.is_final , packet1.command_id );
    mavlink_msg_voice_command_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

#ifdef MAVLINK_HAVE_GET_MESSAGE_INFO
    MAVLINK_ASSERT(mavlink_get_message_info_by_name("VOICE_COMMAND") != NULL);
    MAVLINK_ASSERT(mavlink_get_message_info_by_id(MAVLINK_MSG_ID_VOICE_COMMAND) != NULL);
#endif
}

static void mavlink_test_voice_status(uint8_t system_id, uint8_t component_id, mavlink_message_t *last_msg)
{
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
    mavlink_status_t *status = mavlink_get_channel_status(MAVLINK_COMM_0);
        if ((status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) && MAVLINK_MSG_ID_VOICE_STATUS >= 256) {
            return;
        }
#endif
    mavlink_message_t msg;
        uint8_t buffer[MAVLINK_MAX_PACKET_LEN];
        uint16_t i;
    mavlink_voice_status_t packet_in = {
        963497464,45.0,73.0,963498088,963498296,157.0,77,144,"ABCDEFGHIJKLMNOPQRSTUVWXYZABCDE"
    };
    mavlink_voice_status_t packet1, packet2;
        memset(&packet1, 0, sizeof(packet1));
        packet1.timestamp_ms = packet_in.timestamp_ms;
        packet1.cpu_usage = packet_in.cpu_usage;
        packet1.memory_usage_mb = packet_in.memory_usage_mb;
        packet1.commands_processed = packet_in.commands_processed;
        packet1.commands_failed = packet_in.commands_failed;
        packet1.last_latency_ms = packet_in.last_latency_ms;
        packet1.vad_active = packet_in.vad_active;
        packet1.asr_active = packet_in.asr_active;
        
        mav_array_memcpy(packet1.current_model, packet_in.current_model, sizeof(char)*32);
        
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
        if (status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) {
           // cope with extensions
           memset(MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN + (char *)&packet1, 0, sizeof(packet1)-MAVLINK_MSG_ID_VOICE_STATUS_MIN_LEN);
        }
#endif
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_status_encode(system_id, component_id, &msg, &packet1);
    mavlink_msg_voice_status_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_status_pack(system_id, component_id, &msg , packet1.timestamp_ms , packet1.vad_active , packet1.asr_active , packet1.current_model , packet1.cpu_usage , packet1.memory_usage_mb , packet1.commands_processed , packet1.commands_failed , packet1.last_latency_ms );
    mavlink_msg_voice_status_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_status_pack_chan(system_id, component_id, MAVLINK_COMM_0, &msg , packet1.timestamp_ms , packet1.vad_active , packet1.asr_active , packet1.current_model , packet1.cpu_usage , packet1.memory_usage_mb , packet1.commands_processed , packet1.commands_failed , packet1.last_latency_ms );
    mavlink_msg_voice_status_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
        mavlink_msg_to_send_buffer(buffer, &msg);
        for (i=0; i<mavlink_msg_get_send_buffer_length(&msg); i++) {
            comm_send_ch(MAVLINK_COMM_0, buffer[i]);
        }
    mavlink_msg_voice_status_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);
        
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_status_send(MAVLINK_COMM_1 , packet1.timestamp_ms , packet1.vad_active , packet1.asr_active , packet1.current_model , packet1.cpu_usage , packet1.memory_usage_mb , packet1.commands_processed , packet1.commands_failed , packet1.last_latency_ms );
    mavlink_msg_voice_status_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

#ifdef MAVLINK_HAVE_GET_MESSAGE_INFO
    MAVLINK_ASSERT(mavlink_get_message_info_by_name("VOICE_STATUS") != NULL);
    MAVLINK_ASSERT(mavlink_get_message_info_by_id(MAVLINK_MSG_ID_VOICE_STATUS) != NULL);
#endif
}

static void mavlink_test_voice_feedback(uint8_t system_id, uint8_t component_id, mavlink_message_t *last_msg)
{
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
    mavlink_status_t *status = mavlink_get_channel_status(MAVLINK_COMM_0);
        if ((status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) && MAVLINK_MSG_ID_VOICE_FEEDBACK >= 256) {
            return;
        }
#endif
    mavlink_message_t msg;
        uint8_t buffer[MAVLINK_MAX_PACKET_LEN];
        uint16_t i;
    mavlink_voice_feedback_t packet_in = {
        963497464,45.0,29,96,"KLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTU"
    };
    mavlink_voice_feedback_t packet1, packet2;
        memset(&packet1, 0, sizeof(packet1));
        packet1.timestamp_ms = packet_in.timestamp_ms;
        packet1.progress = packet_in.progress;
        packet1.feedback_type = packet_in.feedback_type;
        packet1.command_id = packet_in.command_id;
        
        mav_array_memcpy(packet1.message, packet_in.message, sizeof(char)*64);
        
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
        if (status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) {
           // cope with extensions
           memset(MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN + (char *)&packet1, 0, sizeof(packet1)-MAVLINK_MSG_ID_VOICE_FEEDBACK_MIN_LEN);
        }
#endif
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_feedback_encode(system_id, component_id, &msg, &packet1);
    mavlink_msg_voice_feedback_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_feedback_pack(system_id, component_id, &msg , packet1.timestamp_ms , packet1.feedback_type , packet1.command_id , packet1.message , packet1.progress );
    mavlink_msg_voice_feedback_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_feedback_pack_chan(system_id, component_id, MAVLINK_COMM_0, &msg , packet1.timestamp_ms , packet1.feedback_type , packet1.command_id , packet1.message , packet1.progress );
    mavlink_msg_voice_feedback_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
        mavlink_msg_to_send_buffer(buffer, &msg);
        for (i=0; i<mavlink_msg_get_send_buffer_length(&msg); i++) {
            comm_send_ch(MAVLINK_COMM_0, buffer[i]);
        }
    mavlink_msg_voice_feedback_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);
        
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_feedback_send(MAVLINK_COMM_1 , packet1.timestamp_ms , packet1.feedback_type , packet1.command_id , packet1.message , packet1.progress );
    mavlink_msg_voice_feedback_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

#ifdef MAVLINK_HAVE_GET_MESSAGE_INFO
    MAVLINK_ASSERT(mavlink_get_message_info_by_name("VOICE_FEEDBACK") != NULL);
    MAVLINK_ASSERT(mavlink_get_message_info_by_id(MAVLINK_MSG_ID_VOICE_FEEDBACK) != NULL);
#endif
}

static void mavlink_test_voice_waypoint(uint8_t system_id, uint8_t component_id, mavlink_message_t *last_msg)
{
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
    mavlink_status_t *status = mavlink_get_channel_status(MAVLINK_COMM_0);
        if ((status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) && MAVLINK_MSG_ID_VOICE_WAYPOINT >= 256) {
            return;
        }
#endif
    mavlink_message_t msg;
        uint8_t buffer[MAVLINK_MAX_PACKET_LEN];
        uint16_t i;
    mavlink_voice_waypoint_t packet_in = {
        963497464,963497672,963497880,963498088,18067,18171,"UVWXYZABCDEFGHIJKLMNOPQRSTUVWXY",161
    };
    mavlink_voice_waypoint_t packet1, packet2;
        memset(&packet1, 0, sizeof(packet1));
        packet1.timestamp_ms = packet_in.timestamp_ms;
        packet1.lat = packet_in.lat;
        packet1.lon = packet_in.lon;
        packet1.alt = packet_in.alt;
        packet1.seq = packet_in.seq;
        packet1.command_id = packet_in.command_id;
        packet1.frame = packet_in.frame;
        
        mav_array_memcpy(packet1.label, packet_in.label, sizeof(char)*32);
        
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
        if (status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) {
           // cope with extensions
           memset(MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN + (char *)&packet1, 0, sizeof(packet1)-MAVLINK_MSG_ID_VOICE_WAYPOINT_MIN_LEN);
        }
#endif
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_waypoint_encode(system_id, component_id, &msg, &packet1);
    mavlink_msg_voice_waypoint_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_waypoint_pack(system_id, component_id, &msg , packet1.timestamp_ms , packet1.seq , packet1.label , packet1.lat , packet1.lon , packet1.alt , packet1.frame , packet1.command_id );
    mavlink_msg_voice_waypoint_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_waypoint_pack_chan(system_id, component_id, MAVLINK_COMM_0, &msg , packet1.timestamp_ms , packet1.seq , packet1.label , packet1.lat , packet1.lon , packet1.alt , packet1.frame , packet1.command_id );
    mavlink_msg_voice_waypoint_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
        mavlink_msg_to_send_buffer(buffer, &msg);
        for (i=0; i<mavlink_msg_get_send_buffer_length(&msg); i++) {
            comm_send_ch(MAVLINK_COMM_0, buffer[i]);
        }
    mavlink_msg_voice_waypoint_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);
        
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_waypoint_send(MAVLINK_COMM_1 , packet1.timestamp_ms , packet1.seq , packet1.label , packet1.lat , packet1.lon , packet1.alt , packet1.frame , packet1.command_id );
    mavlink_msg_voice_waypoint_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

#ifdef MAVLINK_HAVE_GET_MESSAGE_INFO
    MAVLINK_ASSERT(mavlink_get_message_info_by_name("VOICE_WAYPOINT") != NULL);
    MAVLINK_ASSERT(mavlink_get_message_info_by_id(MAVLINK_MSG_ID_VOICE_WAYPOINT) != NULL);
#endif
}

static void mavlink_test_voice_emergency(uint8_t system_id, uint8_t component_id, mavlink_message_t *last_msg)
{
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
    mavlink_status_t *status = mavlink_get_channel_status(MAVLINK_COMM_0);
        if ((status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) && MAVLINK_MSG_ID_VOICE_EMERGENCY >= 256) {
            return;
        }
#endif
    mavlink_message_t msg;
        uint8_t buffer[MAVLINK_MAX_PACKET_LEN];
        uint16_t i;
    mavlink_voice_emergency_t packet_in = {
        963497464,45.0,"IJKLMNOPQRSTUVW",77
    };
    mavlink_voice_emergency_t packet1, packet2;
        memset(&packet1, 0, sizeof(packet1));
        packet1.timestamp_ms = packet_in.timestamp_ms;
        packet1.confidence = packet_in.confidence;
        packet1.source = packet_in.source;
        
        mav_array_memcpy(packet1.emergency_type, packet_in.emergency_type, sizeof(char)*16);
        
#ifdef MAVLINK_STATUS_FLAG_OUT_MAVLINK1
        if (status->flags & MAVLINK_STATUS_FLAG_OUT_MAVLINK1) {
           // cope with extensions
           memset(MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN + (char *)&packet1, 0, sizeof(packet1)-MAVLINK_MSG_ID_VOICE_EMERGENCY_MIN_LEN);
        }
#endif
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_emergency_encode(system_id, component_id, &msg, &packet1);
    mavlink_msg_voice_emergency_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_emergency_pack(system_id, component_id, &msg , packet1.timestamp_ms , packet1.emergency_type , packet1.confidence , packet1.source );
    mavlink_msg_voice_emergency_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_emergency_pack_chan(system_id, component_id, MAVLINK_COMM_0, &msg , packet1.timestamp_ms , packet1.emergency_type , packet1.confidence , packet1.source );
    mavlink_msg_voice_emergency_decode(&msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

        memset(&packet2, 0, sizeof(packet2));
        mavlink_msg_to_send_buffer(buffer, &msg);
        for (i=0; i<mavlink_msg_get_send_buffer_length(&msg); i++) {
            comm_send_ch(MAVLINK_COMM_0, buffer[i]);
        }
    mavlink_msg_voice_emergency_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);
        
        memset(&packet2, 0, sizeof(packet2));
    mavlink_msg_voice_emergency_send(MAVLINK_COMM_1 , packet1.timestamp_ms , packet1.emergency_type , packet1.confidence , packet1.source );
    mavlink_msg_voice_emergency_decode(last_msg, &packet2);
        MAVLINK_ASSERT(memcmp(&packet1, &packet2, sizeof(packet1)) == 0);

#ifdef MAVLINK_HAVE_GET_MESSAGE_INFO
    MAVLINK_ASSERT(mavlink_get_message_info_by_name("VOICE_EMERGENCY") != NULL);
    MAVLINK_ASSERT(mavlink_get_message_info_by_id(MAVLINK_MSG_ID_VOICE_EMERGENCY) != NULL);
#endif
}

static void mavlink_test_voice_control(uint8_t system_id, uint8_t component_id, mavlink_message_t *last_msg)
{
    mavlink_test_voice_command(system_id, component_id, last_msg);
    mavlink_test_voice_status(system_id, component_id, last_msg);
    mavlink_test_voice_feedback(system_id, component_id, last_msg);
    mavlink_test_voice_waypoint(system_id, component_id, last_msg);
    mavlink_test_voice_emergency(system_id, component_id, last_msg);
}

#ifdef __cplusplus
}
#endif // __cplusplus
#endif // VOICE_CONTROL_TESTSUITE_H
