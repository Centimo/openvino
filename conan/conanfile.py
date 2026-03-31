import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, rmdir

required_conan_version = ">=2.1"


class OpenvinoConan(ConanFile):
    name = "openvino"
    version = "2026.0.2"

    license = "Apache-2.0"
    homepage = "https://github.com/openvinotoolkit/openvino"
    url = "https://github.com/openvinotoolkit/openvino"
    description = "Open Visual Inference And Optimization toolkit for AI inference"
    topics = ("deep-learning", "inference", "computer-vision", "ai")

    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "enable_cpu": [True, False],
        "enable_auto": [True, False],
        "enable_hetero": [True, False],
        "enable_auto_batch": [True, False],
        "enable_ir_frontend": [True, False],
        "enable_onnx_frontend": [True, False],
        "enable_tf_frontend": [True, False],
        "enable_tf_lite_frontend": [True, False],
        "enable_paddle_frontend": [True, False],
        "enable_pytorch_frontend": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "enable_cpu": True,
        "enable_auto": True,
        "enable_hetero": True,
        "enable_auto_batch": True,
        "enable_ir_frontend": True,
        "enable_onnx_frontend": True,
        "enable_tf_frontend": False,
        "enable_tf_lite_frontend": False,
        "enable_paddle_frontend": False,
        "enable_pytorch_frontend": False,
    }

    @property
    def _target_x86_64(self):
        return self.settings.arch == "x86_64"

    def export_sources(self):
        export_conandata_patches(self)
        copy(self, "*", src=os.path.join(self.recipe_folder, ".."), dst=self.export_sources_folder,
             excludes=["conan/*", ".git/*",
                       "src/plugins/intel_gpu/thirdparty/onednn_gpu/*"])

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        self.requires("onetbb/2021.10.0")
        self.requires("pugixml/1.14")
        self.requires("nlohmann_json/3.11.3")
        if self._target_x86_64:
            self.requires("xbyak/6.73")
        if self.options.enable_tf_lite_frontend:
            self.requires("flatbuffers/23.5.26")

    def build_requirements(self):
        if self.options.enable_tf_lite_frontend:
            self.tool_requires("flatbuffers/<host_version>")
        self.tool_requires("cmake/3.28.3", override=True)

    def validate_build(self):
        check_min_cppstd(self, "17")
        if self.settings.compiler == "clang" and self.settings.compiler.libcxx == "libc++":
            raise ConanInvalidConfiguration(
                f"{self.ref} cannot be built with clang and libc++ due to unresolved symbols."
            )

    def source(self):
        if os.path.exists(os.path.join(self.source_folder, "cmake", "features.cmake")):
            self.output.info("Sources found in source_folder (from export_sources), skipping download")
        else:
            self.output.error(f"Sources not found in {self.source_folder}")
        apply_conandata_patches(self)


    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()

        toolchain = CMakeToolchain(self)
        # HW plugins
        toolchain.cache_variables["ENABLE_INTEL_CPU"] = self.options.enable_cpu
        toolchain.cache_variables["ENABLE_INTEL_GPU"] = False
        toolchain.cache_variables["ENABLE_ONEDNN_FOR_GPU"] = False
        toolchain.cache_variables["ENABLE_INTEL_NPU"] = False
        # SW plugins
        toolchain.cache_variables["ENABLE_AUTO"] = self.options.enable_auto
        toolchain.cache_variables["ENABLE_MULTI"] = self.options.enable_auto
        toolchain.cache_variables["ENABLE_AUTO_BATCH"] = self.options.enable_auto_batch
        toolchain.cache_variables["ENABLE_HETERO"] = self.options.enable_hetero
        # Frontends
        toolchain.cache_variables["ENABLE_OV_IR_FRONTEND"] = self.options.enable_ir_frontend
        toolchain.cache_variables["ENABLE_OV_ONNX_FRONTEND"] = self.options.enable_onnx_frontend
        toolchain.cache_variables["ENABLE_OV_TF_FRONTEND"] = self.options.enable_tf_frontend
        toolchain.cache_variables["ENABLE_OV_TF_LITE_FRONTEND"] = self.options.enable_tf_lite_frontend
        toolchain.cache_variables["ENABLE_OV_PADDLE_FRONTEND"] = self.options.enable_paddle_frontend
        toolchain.cache_variables["ENABLE_OV_PYTORCH_FRONTEND"] = self.options.enable_pytorch_frontend
        toolchain.cache_variables["ENABLE_OV_JAX_FRONTEND"] = False
        # System dependencies — use bundled onnx and protobuf to avoid version conflicts
        toolchain.cache_variables["ENABLE_SYSTEM_TBB"] = True
        toolchain.cache_variables["ENABLE_TBBBIND_2_5"] = False
        toolchain.cache_variables["ENABLE_SYSTEM_PUGIXML"] = True
        toolchain.cache_variables["ENABLE_SYSTEM_PROTOBUF"] = False
        toolchain.cache_variables["ENABLE_SYSTEM_OPENCL"] = False
        if self.options.enable_tf_lite_frontend:
            toolchain.cache_variables["ENABLE_SYSTEM_FLATBUFFERS"] = True
        # Misc
        toolchain.cache_variables["BUILD_SHARED_LIBS"] = self.options.shared
        toolchain.cache_variables["CPACK_GENERATOR"] = "CONAN"
        toolchain.cache_variables["ENABLE_PROFILING_ITT"] = False
        toolchain.cache_variables["ENABLE_PYTHON"] = False
        toolchain.cache_variables["ENABLE_PROXY"] = False
        toolchain.cache_variables["ENABLE_WHEEL"] = False
        toolchain.cache_variables["ENABLE_CPPLINT"] = False
        toolchain.cache_variables["ENABLE_NCC_STYLE"] = False
        toolchain.cache_variables["ENABLE_SAMPLES"] = False
        toolchain.cache_variables["ENABLE_TEMPLATE"] = False
        toolchain.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        for target in ["ov_frontends", "ov_plugins", "openvino_c"]:
            cmake.build(target=target)

    def package(self):
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "share"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))

    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "config")
        self.cpp_info.set_property("cmake_file_name", "OpenVINO")
        self.cpp_info.set_property("pkg_config_name", "openvino")

        lib_suffix = ""
        if self.settings.build_type == "Debug" and self.settings.os in ("Windows", "Macos"):
            lib_suffix = "d"

        openvino_runtime = self.cpp_info.components["Runtime"]
        openvino_runtime.set_property("cmake_target_name", "openvino::runtime")
        openvino_runtime.requires = ["onetbb::libtbb", "pugixml::pugixml", "nlohmann_json::nlohmann_json"]
        openvino_runtime.libs = [f"openvino{lib_suffix}"]
        if self._target_x86_64:
            openvino_runtime.requires.append("xbyak::xbyak")
        if self.settings.os in ["Linux", "Android", "FreeBSD", "SunOS", "AIX"]:
            openvino_runtime.system_libs = ["m", "dl", "pthread"]
        if self.settings.os == "Windows":
            openvino_runtime.system_libs = ["shlwapi"]

        if not self.options.shared:
            if self.options.enable_cpu:
                openvino_runtime.libs.extend([
                    f"openvino_intel_cpu_plugin{lib_suffix}",
                    f"openvino_onednn_cpu{lib_suffix}",
                    f"openvino_snippets{lib_suffix}",
                    f"mlas{lib_suffix}",
                    f"openvino_xml_util{lib_suffix}",
                ])
            if self.options.enable_auto:
                openvino_runtime.libs.append(f"openvino_auto_plugin{lib_suffix}")
            if self.options.enable_hetero:
                openvino_runtime.libs.append(f"openvino_hetero_plugin{lib_suffix}")
            if self.options.enable_auto_batch:
                openvino_runtime.libs.append(f"openvino_auto_batch_plugin{lib_suffix}")
            if self.options.enable_ir_frontend:
                openvino_runtime.libs.append(f"openvino_ir_frontend{lib_suffix}")
            if self.options.enable_onnx_frontend:
                openvino_runtime.libs.extend([
                    f"openvino_onnx_frontend{lib_suffix}",
                    f"openvino_onnx_common{lib_suffix}",
                ])
            if self.options.enable_tf_frontend:
                openvino_runtime.libs.append(f"openvino_tensorflow_frontend{lib_suffix}")
            if self.options.enable_tf_lite_frontend:
                openvino_runtime.libs.append(f"openvino_tensorflow_lite_frontend{lib_suffix}")
                openvino_runtime.requires.append("flatbuffers::flatbuffers")
            if self.options.enable_tf_frontend or self.options.enable_tf_lite_frontend:
                openvino_runtime.libs.append(f"openvino_tensorflow_common{lib_suffix}")
            if self.options.enable_paddle_frontend:
                openvino_runtime.libs.append(f"openvino_paddle_frontend{lib_suffix}")
            if self.options.enable_pytorch_frontend:
                openvino_runtime.libs.append(f"openvino_pytorch_frontend{lib_suffix}")
            openvino_runtime.libs.extend([
                f"openvino_reference{lib_suffix}",
                f"openvino_shape_inference{lib_suffix}",
                f"openvino_itt{lib_suffix}",
                f"openvino_common_translators{lib_suffix}",
                f"openvino_util{lib_suffix}",
            ])
            full_openvino_lib_path = (
                os.path.join(self.package_folder, "lib", f"openvino{lib_suffix}.lib").replace("\\", "/")
                if self.settings.os == "Windows"
                else os.path.join(self.package_folder, "lib", f"libopenvino{lib_suffix}.a")
            )
            openvino_runtime.system_libs.insert(0, full_openvino_lib_path)
            openvino_runtime.defines = ["OPENVINO_STATIC_LIBRARY"]

        openvino_runtime_c = self.cpp_info.components["Runtime_C"]
        openvino_runtime_c.set_property("cmake_target_name", "openvino::runtime::c")
        openvino_runtime_c.libs = [f"openvino_c{lib_suffix}"]
        openvino_runtime_c.requires = ["Runtime"]

        if self.options.enable_onnx_frontend:
            openvino_onnx = self.cpp_info.components["ONNX"]
            openvino_onnx.set_property("cmake_target_name", "openvino::frontend::onnx")
            openvino_onnx.libs = [f"openvino_onnx_frontend{lib_suffix}"]
            openvino_onnx.requires = ["Runtime"]

        if self.options.enable_tf_frontend:
            openvino_tensorflow = self.cpp_info.components["TensorFlow"]
            openvino_tensorflow.set_property("cmake_target_name", "openvino::frontend::tensorflow")
            openvino_tensorflow.libs = [f"openvino_tensorflow_frontend{lib_suffix}"]
            openvino_tensorflow.requires = ["Runtime"]

        if self.options.enable_pytorch_frontend:
            openvino_pytorch = self.cpp_info.components["PyTorch"]
            openvino_pytorch.set_property("cmake_target_name", "openvino::frontend::pytorch")
            openvino_pytorch.libs = [f"openvino_pytorch_frontend{lib_suffix}"]
            openvino_pytorch.requires = ["Runtime"]

        if self.options.enable_tf_lite_frontend:
            openvino_tensorflow_lite = self.cpp_info.components["TensorFlowLite"]
            openvino_tensorflow_lite.set_property("cmake_target_name", "openvino::frontend::tensorflow_lite")
            openvino_tensorflow_lite.libs = [f"openvino_tensorflow_lite_frontend{lib_suffix}"]
            openvino_tensorflow_lite.requires = ["Runtime", "flatbuffers::flatbuffers"]
