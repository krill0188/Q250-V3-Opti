/** @file
 *  @brief MAVLink comm testsuite protocol generated from voice_control.xml
 *  @see http://mavlink.org
 */

#pragma once

#include <gtest/gtest.h>
#include "voice_control.hpp"

#ifdef TEST_INTEROP
using namespace mavlink;
#undef MAVLINK_HELPER
#include "mavlink.h"
#endif


TEST(voice_control, VOICE_COMMAND)
{
    mavlink::mavlink_message_t msg;
    mavlink::MsgMap map1(msg);
    mavlink::MsgMap map2(msg);

    mavlink::voice_control::msg::VOICE_COMMAND packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.command_text = to_char_array("WXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRS");
    packet_in.parsed_action = to_char_array("UVWXYZABCDEFGHIJKLMNOPQRSTUVWXY");
    packet_in.params = {{ 45.0, 46.0, 47.0, 48.0, 49.0, 50.0, 51.0, 52.0, 53.0, 54.0 }};
    packet_in.param_count = 117;
    packet_in.confidence = 325.0;
    packet_in.is_final = 184;
    packet_in.command_id = 251;

    mavlink::voice_control::msg::VOICE_COMMAND packet1{};
    mavlink::voice_control::msg::VOICE_COMMAND packet2{};

    packet1 = packet_in;

    //std::cout << packet1.to_yaml() << std::endl;

    packet1.serialize(map1);

    mavlink::mavlink_finalize_message(&msg, 1, 1, packet1.MIN_LENGTH, packet1.LENGTH, packet1.CRC_EXTRA);

    packet2.deserialize(map2);

    EXPECT_EQ(packet1.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet1.command_text, packet2.command_text);
    EXPECT_EQ(packet1.parsed_action, packet2.parsed_action);
    EXPECT_EQ(packet1.params, packet2.params);
    EXPECT_EQ(packet1.param_count, packet2.param_count);
    EXPECT_EQ(packet1.confidence, packet2.confidence);
    EXPECT_EQ(packet1.is_final, packet2.is_final);
    EXPECT_EQ(packet1.command_id, packet2.command_id);
}

#ifdef TEST_INTEROP
TEST(voice_control_interop, VOICE_COMMAND)
{
    mavlink_message_t msg;

    // to get nice print
    memset(&msg, 0, sizeof(msg));

    mavlink_voice_command_t packet_c {
         963497464, { 45.0, 46.0, 47.0, 48.0, 49.0, 50.0, 51.0, 52.0, 53.0, 54.0 }, 325.0, "WXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRS", "UVWXYZABCDEFGHIJKLMNOPQRSTUVWXY", 117, 184, 251
    };

    mavlink::voice_control::msg::VOICE_COMMAND packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.command_text = to_char_array("WXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRS");
    packet_in.parsed_action = to_char_array("UVWXYZABCDEFGHIJKLMNOPQRSTUVWXY");
    packet_in.params = {{ 45.0, 46.0, 47.0, 48.0, 49.0, 50.0, 51.0, 52.0, 53.0, 54.0 }};
    packet_in.param_count = 117;
    packet_in.confidence = 325.0;
    packet_in.is_final = 184;
    packet_in.command_id = 251;

    mavlink::voice_control::msg::VOICE_COMMAND packet2{};

    mavlink_msg_voice_command_encode(1, 1, &msg, &packet_c);

    // simulate message-handling callback
    [&packet2](const mavlink_message_t *cmsg) {
        MsgMap map2(cmsg);

        packet2.deserialize(map2);
    } (&msg);

    EXPECT_EQ(packet_in.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet_in.command_text, packet2.command_text);
    EXPECT_EQ(packet_in.parsed_action, packet2.parsed_action);
    EXPECT_EQ(packet_in.params, packet2.params);
    EXPECT_EQ(packet_in.param_count, packet2.param_count);
    EXPECT_EQ(packet_in.confidence, packet2.confidence);
    EXPECT_EQ(packet_in.is_final, packet2.is_final);
    EXPECT_EQ(packet_in.command_id, packet2.command_id);

#ifdef PRINT_MSG
    PRINT_MSG(msg);
#endif
}
#endif

TEST(voice_control, VOICE_STATUS)
{
    mavlink::mavlink_message_t msg;
    mavlink::MsgMap map1(msg);
    mavlink::MsgMap map2(msg);

    mavlink::voice_control::msg::VOICE_STATUS packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.vad_active = 77;
    packet_in.asr_active = 144;
    packet_in.current_model = to_char_array("ABCDEFGHIJKLMNOPQRSTUVWXYZABCDE");
    packet_in.cpu_usage = 45.0;
    packet_in.memory_usage_mb = 73.0;
    packet_in.commands_processed = 963498088;
    packet_in.commands_failed = 963498296;
    packet_in.last_latency_ms = 157.0;

    mavlink::voice_control::msg::VOICE_STATUS packet1{};
    mavlink::voice_control::msg::VOICE_STATUS packet2{};

    packet1 = packet_in;

    //std::cout << packet1.to_yaml() << std::endl;

    packet1.serialize(map1);

    mavlink::mavlink_finalize_message(&msg, 1, 1, packet1.MIN_LENGTH, packet1.LENGTH, packet1.CRC_EXTRA);

    packet2.deserialize(map2);

    EXPECT_EQ(packet1.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet1.vad_active, packet2.vad_active);
    EXPECT_EQ(packet1.asr_active, packet2.asr_active);
    EXPECT_EQ(packet1.current_model, packet2.current_model);
    EXPECT_EQ(packet1.cpu_usage, packet2.cpu_usage);
    EXPECT_EQ(packet1.memory_usage_mb, packet2.memory_usage_mb);
    EXPECT_EQ(packet1.commands_processed, packet2.commands_processed);
    EXPECT_EQ(packet1.commands_failed, packet2.commands_failed);
    EXPECT_EQ(packet1.last_latency_ms, packet2.last_latency_ms);
}

#ifdef TEST_INTEROP
TEST(voice_control_interop, VOICE_STATUS)
{
    mavlink_message_t msg;

    // to get nice print
    memset(&msg, 0, sizeof(msg));

    mavlink_voice_status_t packet_c {
         963497464, 45.0, 73.0, 963498088, 963498296, 157.0, 77, 144, "ABCDEFGHIJKLMNOPQRSTUVWXYZABCDE"
    };

    mavlink::voice_control::msg::VOICE_STATUS packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.vad_active = 77;
    packet_in.asr_active = 144;
    packet_in.current_model = to_char_array("ABCDEFGHIJKLMNOPQRSTUVWXYZABCDE");
    packet_in.cpu_usage = 45.0;
    packet_in.memory_usage_mb = 73.0;
    packet_in.commands_processed = 963498088;
    packet_in.commands_failed = 963498296;
    packet_in.last_latency_ms = 157.0;

    mavlink::voice_control::msg::VOICE_STATUS packet2{};

    mavlink_msg_voice_status_encode(1, 1, &msg, &packet_c);

    // simulate message-handling callback
    [&packet2](const mavlink_message_t *cmsg) {
        MsgMap map2(cmsg);

        packet2.deserialize(map2);
    } (&msg);

    EXPECT_EQ(packet_in.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet_in.vad_active, packet2.vad_active);
    EXPECT_EQ(packet_in.asr_active, packet2.asr_active);
    EXPECT_EQ(packet_in.current_model, packet2.current_model);
    EXPECT_EQ(packet_in.cpu_usage, packet2.cpu_usage);
    EXPECT_EQ(packet_in.memory_usage_mb, packet2.memory_usage_mb);
    EXPECT_EQ(packet_in.commands_processed, packet2.commands_processed);
    EXPECT_EQ(packet_in.commands_failed, packet2.commands_failed);
    EXPECT_EQ(packet_in.last_latency_ms, packet2.last_latency_ms);

#ifdef PRINT_MSG
    PRINT_MSG(msg);
#endif
}
#endif

TEST(voice_control, VOICE_FEEDBACK)
{
    mavlink::mavlink_message_t msg;
    mavlink::MsgMap map1(msg);
    mavlink::MsgMap map2(msg);

    mavlink::voice_control::msg::VOICE_FEEDBACK packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.feedback_type = 29;
    packet_in.command_id = 96;
    packet_in.message = to_char_array("KLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTU");
    packet_in.progress = 45.0;

    mavlink::voice_control::msg::VOICE_FEEDBACK packet1{};
    mavlink::voice_control::msg::VOICE_FEEDBACK packet2{};

    packet1 = packet_in;

    //std::cout << packet1.to_yaml() << std::endl;

    packet1.serialize(map1);

    mavlink::mavlink_finalize_message(&msg, 1, 1, packet1.MIN_LENGTH, packet1.LENGTH, packet1.CRC_EXTRA);

    packet2.deserialize(map2);

    EXPECT_EQ(packet1.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet1.feedback_type, packet2.feedback_type);
    EXPECT_EQ(packet1.command_id, packet2.command_id);
    EXPECT_EQ(packet1.message, packet2.message);
    EXPECT_EQ(packet1.progress, packet2.progress);
}

#ifdef TEST_INTEROP
TEST(voice_control_interop, VOICE_FEEDBACK)
{
    mavlink_message_t msg;

    // to get nice print
    memset(&msg, 0, sizeof(msg));

    mavlink_voice_feedback_t packet_c {
         963497464, 45.0, 29, 96, "KLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTU"
    };

    mavlink::voice_control::msg::VOICE_FEEDBACK packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.feedback_type = 29;
    packet_in.command_id = 96;
    packet_in.message = to_char_array("KLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTU");
    packet_in.progress = 45.0;

    mavlink::voice_control::msg::VOICE_FEEDBACK packet2{};

    mavlink_msg_voice_feedback_encode(1, 1, &msg, &packet_c);

    // simulate message-handling callback
    [&packet2](const mavlink_message_t *cmsg) {
        MsgMap map2(cmsg);

        packet2.deserialize(map2);
    } (&msg);

    EXPECT_EQ(packet_in.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet_in.feedback_type, packet2.feedback_type);
    EXPECT_EQ(packet_in.command_id, packet2.command_id);
    EXPECT_EQ(packet_in.message, packet2.message);
    EXPECT_EQ(packet_in.progress, packet2.progress);

#ifdef PRINT_MSG
    PRINT_MSG(msg);
#endif
}
#endif

TEST(voice_control, VOICE_WAYPOINT)
{
    mavlink::mavlink_message_t msg;
    mavlink::MsgMap map1(msg);
    mavlink::MsgMap map2(msg);

    mavlink::voice_control::msg::VOICE_WAYPOINT packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.seq = 18067;
    packet_in.label = to_char_array("UVWXYZABCDEFGHIJKLMNOPQRSTUVWXY");
    packet_in.lat = 963497672;
    packet_in.lon = 963497880;
    packet_in.alt = 963498088;
    packet_in.frame = 161;
    packet_in.command_id = 18171;

    mavlink::voice_control::msg::VOICE_WAYPOINT packet1{};
    mavlink::voice_control::msg::VOICE_WAYPOINT packet2{};

    packet1 = packet_in;

    //std::cout << packet1.to_yaml() << std::endl;

    packet1.serialize(map1);

    mavlink::mavlink_finalize_message(&msg, 1, 1, packet1.MIN_LENGTH, packet1.LENGTH, packet1.CRC_EXTRA);

    packet2.deserialize(map2);

    EXPECT_EQ(packet1.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet1.seq, packet2.seq);
    EXPECT_EQ(packet1.label, packet2.label);
    EXPECT_EQ(packet1.lat, packet2.lat);
    EXPECT_EQ(packet1.lon, packet2.lon);
    EXPECT_EQ(packet1.alt, packet2.alt);
    EXPECT_EQ(packet1.frame, packet2.frame);
    EXPECT_EQ(packet1.command_id, packet2.command_id);
}

#ifdef TEST_INTEROP
TEST(voice_control_interop, VOICE_WAYPOINT)
{
    mavlink_message_t msg;

    // to get nice print
    memset(&msg, 0, sizeof(msg));

    mavlink_voice_waypoint_t packet_c {
         963497464, 963497672, 963497880, 963498088, 18067, 18171, "UVWXYZABCDEFGHIJKLMNOPQRSTUVWXY", 161
    };

    mavlink::voice_control::msg::VOICE_WAYPOINT packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.seq = 18067;
    packet_in.label = to_char_array("UVWXYZABCDEFGHIJKLMNOPQRSTUVWXY");
    packet_in.lat = 963497672;
    packet_in.lon = 963497880;
    packet_in.alt = 963498088;
    packet_in.frame = 161;
    packet_in.command_id = 18171;

    mavlink::voice_control::msg::VOICE_WAYPOINT packet2{};

    mavlink_msg_voice_waypoint_encode(1, 1, &msg, &packet_c);

    // simulate message-handling callback
    [&packet2](const mavlink_message_t *cmsg) {
        MsgMap map2(cmsg);

        packet2.deserialize(map2);
    } (&msg);

    EXPECT_EQ(packet_in.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet_in.seq, packet2.seq);
    EXPECT_EQ(packet_in.label, packet2.label);
    EXPECT_EQ(packet_in.lat, packet2.lat);
    EXPECT_EQ(packet_in.lon, packet2.lon);
    EXPECT_EQ(packet_in.alt, packet2.alt);
    EXPECT_EQ(packet_in.frame, packet2.frame);
    EXPECT_EQ(packet_in.command_id, packet2.command_id);

#ifdef PRINT_MSG
    PRINT_MSG(msg);
#endif
}
#endif

TEST(voice_control, VOICE_EMERGENCY)
{
    mavlink::mavlink_message_t msg;
    mavlink::MsgMap map1(msg);
    mavlink::MsgMap map2(msg);

    mavlink::voice_control::msg::VOICE_EMERGENCY packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.emergency_type = to_char_array("IJKLMNOPQRSTUVW");
    packet_in.confidence = 45.0;
    packet_in.source = 77;

    mavlink::voice_control::msg::VOICE_EMERGENCY packet1{};
    mavlink::voice_control::msg::VOICE_EMERGENCY packet2{};

    packet1 = packet_in;

    //std::cout << packet1.to_yaml() << std::endl;

    packet1.serialize(map1);

    mavlink::mavlink_finalize_message(&msg, 1, 1, packet1.MIN_LENGTH, packet1.LENGTH, packet1.CRC_EXTRA);

    packet2.deserialize(map2);

    EXPECT_EQ(packet1.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet1.emergency_type, packet2.emergency_type);
    EXPECT_EQ(packet1.confidence, packet2.confidence);
    EXPECT_EQ(packet1.source, packet2.source);
}

#ifdef TEST_INTEROP
TEST(voice_control_interop, VOICE_EMERGENCY)
{
    mavlink_message_t msg;

    // to get nice print
    memset(&msg, 0, sizeof(msg));

    mavlink_voice_emergency_t packet_c {
         963497464, 45.0, "IJKLMNOPQRSTUVW", 77
    };

    mavlink::voice_control::msg::VOICE_EMERGENCY packet_in{};
    packet_in.timestamp_ms = 963497464;
    packet_in.emergency_type = to_char_array("IJKLMNOPQRSTUVW");
    packet_in.confidence = 45.0;
    packet_in.source = 77;

    mavlink::voice_control::msg::VOICE_EMERGENCY packet2{};

    mavlink_msg_voice_emergency_encode(1, 1, &msg, &packet_c);

    // simulate message-handling callback
    [&packet2](const mavlink_message_t *cmsg) {
        MsgMap map2(cmsg);

        packet2.deserialize(map2);
    } (&msg);

    EXPECT_EQ(packet_in.timestamp_ms, packet2.timestamp_ms);
    EXPECT_EQ(packet_in.emergency_type, packet2.emergency_type);
    EXPECT_EQ(packet_in.confidence, packet2.confidence);
    EXPECT_EQ(packet_in.source, packet2.source);

#ifdef PRINT_MSG
    PRINT_MSG(msg);
#endif
}
#endif
