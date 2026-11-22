cmake_minimum_required(VERSION 3.18)
project(trajectory_kernels LANGUAGES CUDA CXX)

# CUDA 아키텍처 설정 (Jetson Orin = sm_87, RTX 30/40 = sm_86/89)
set(CMAKE_CUDA_ARCHITECTURES "87;86;89;90" CACHE STRING "CUDA architectures")

# C++ 표준
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# CUDA 표준
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

# 출력 디렉토리
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

# 공유 라이브러리 생성
add_library(trajectory_kernels SHARED
    src/cuda/trajectory_kernels.cu
)

# 포함 디렉토리
target_include_directories(trajectory_kernels PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cuda
)

# CUDA 컴파일 옵션
target_compile_options(trajectory_kernels PRIVATE
    $<$<COMPILE_LANGUAGE:CUDA>:
        -O3
        -use_fast_math
        -Xptxas -O3
        -maxrregcount=64
        -lineinfo
    >
)

# 링크 라이브러리
target_link_libraries(trajectory_kernels PUBLIC
    ${CUDA_LIBRARIES}
    cudart
)

# 설치 설정
install(TARGETS trajectory_kernels
    LIBRARY DESTINATION lib
)

# Python 바인딩 설치를 위한 커스텀 타겟
add_custom_target(install_python_bindings
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        ${CMAKE_CURRENT_SOURCE_DIR}/src/cuda/trajectory_bindings.py
        ${CMAKE_CURRENT_BINARY_DIR}/trajectory_bindings.py
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        ${CMAKE_CURRENT_SOURCE_DIR}/src/cuda/trajectory_kernels.cuh
        ${CMAKE_CURRENT_BINARY_DIR}/trajectory_kernels.cuh
    COMMENT "Installing Python bindings"
)

# 테스트 실행 파일 (선택사항)
if(BUILD_TESTING)
    enable_testing()
    
    add_executable(test_trajectory_kernels
        src/cuda/test_trajectory_kernels.cu
    )
    target_link_libraries(test_trajectory_kernels PRIVATE trajectory_kernels)
    add_test(NAME trajectory_kernels_test COMMAND test_trajectory_kernels)
endif()

# 패키지 설정
set(CPACK_PACKAGE_NAME "q250-trajectory-kernels")
set(CPACK_PACKAGE_VERSION "1.0.0")
set(CPACK_PACKAGE_DESCRIPTION "Q250-V3-Opti Trajectory CUDA Kernels")
include(CPack)