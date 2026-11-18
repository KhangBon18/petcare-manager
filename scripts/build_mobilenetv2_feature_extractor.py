#!/usr/bin/env python3
"""Reproducible builder for the dual-output MobileNetV2-12 ONNX feature extractor (AI-4.0c).

Preserves the upstream ``mobilenetv2-12.onnx`` artifact untouched on disk, verifies its
penultimate 1280-dimensional feature tensor ``"472"`` (output of ``GlobalAveragePool_97`` +
``Reshape_103`` directly feeding ``Gemm_104`` ``classifier.1.weight [1000, 1280]``), and
emits ``mobilenetv2-12-features.onnx`` exposing both ``output [batch_size, 1000]`` and
``embedding_1280 [batch_size, 1280]`` in a single CPUExecutionProvider forward pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "petcare" / "vision" / "models"
BASE_MODEL_PATH = MODELS_DIR / "mobilenetv2-12.onnx"
VARIANT_MODEL_PATH = MODELS_DIR / "mobilenetv2-12-features.onnx"
MANIFEST_PATH = MODELS_DIR / "MODEL_MANIFEST.json"

EXPECTED_BASE_SHA256 = "c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5"
PENULTIMATE_TENSOR_NAME = "472"
EXPOSED_EMBEDDING_NAME = "embedding_1280"
EXPECTED_EMBEDDING_DIM = 1280


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_onnx_proto_classes() -> tuple[Any, Any]:
    fdp = descriptor_pb2.FileDescriptorProto(
        name="petcare_onnx_inspect.proto",
        package="petcare_onnx_inspect",
        syntax="proto3",
    )
    opt = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    rep = descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
    i64 = descriptor_pb2.FieldDescriptorProto.TYPE_INT64
    i32 = descriptor_pb2.FieldDescriptorProto.TYPE_INT32
    s_t = descriptor_pb2.FieldDescriptorProto.TYPE_STRING
    b_t = descriptor_pb2.FieldDescriptorProto.TYPE_BYTES
    f_t = descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT
    m_t = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE

    def add_msg(name: str, fields: list[tuple[str, int, int, int, str | None]]) -> None:
        msg = fdp.message_type.add(name=name)
        for fname, num, label, ftype, tname in fields:
            fld = msg.field.add(name=fname, number=num, label=label, type=ftype)
            if tname:
                fld.type_name = tname

    add_msg("Dimension", [("dim_value", 1, opt, i64, None), ("dim_param", 2, opt, s_t, None)])
    add_msg("TensorShapeProto", [("dim", 1, rep, m_t, ".petcare_onnx_inspect.Dimension")])
    add_msg(
        "TypeTensor",
        [("elem_type", 1, opt, i32, None), ("shape", 2, opt, m_t, ".petcare_onnx_inspect.TensorShapeProto")],
    )
    add_msg("TypeProto", [("tensor_type", 1, opt, m_t, ".petcare_onnx_inspect.TypeTensor")])
    add_msg(
        "ValueInfoProto",
        [("name", 1, opt, s_t, None), ("type", 2, opt, m_t, ".petcare_onnx_inspect.TypeProto")],
    )
    add_msg(
        "NodeProto",
        [
            ("input", 1, rep, s_t, None),
            ("output", 2, rep, s_t, None),
            ("name", 3, opt, s_t, None),
            ("op_type", 4, opt, s_t, None),
        ],
    )
    add_msg(
        "TensorProto",
        [
            ("dims", 1, rep, i64, None),
            ("data_type", 2, opt, i32, None),
            ("float_data", 4, rep, f_t, None),
            ("name", 8, opt, s_t, None),
            ("raw_data", 9, opt, b_t, None),
        ],
    )
    add_msg(
        "GraphProto",
        [
            ("node", 1, rep, m_t, ".petcare_onnx_inspect.NodeProto"),
            ("name", 2, opt, s_t, None),
            ("initializer", 5, rep, m_t, ".petcare_onnx_inspect.TensorProto"),
            ("input", 11, rep, m_t, ".petcare_onnx_inspect.ValueInfoProto"),
            ("output", 12, rep, m_t, ".petcare_onnx_inspect.ValueInfoProto"),
        ],
    )
    add_msg(
        "ModelProto",
        [
            ("ir_version", 1, opt, i64, None),
            ("producer_name", 2, opt, s_t, None),
            ("graph", 7, opt, m_t, ".petcare_onnx_inspect.GraphProto"),
        ],
    )
    add_msg(
        "GraphAppendix",
        [
            ("node", 1, rep, m_t, ".petcare_onnx_inspect.NodeProto"),
            ("output", 12, rep, m_t, ".petcare_onnx_inspect.ValueInfoProto"),
        ],
    )

    pool = descriptor_pool.DescriptorPool()
    pool.Add(fdp)
    model_cls = message_factory.GetMessageClass(
        pool.FindMessageTypeByName("petcare_onnx_inspect.ModelProto")
    )
    appendix_cls = message_factory.GetMessageClass(
        pool.FindMessageTypeByName("petcare_onnx_inspect.GraphAppendix")
    )
    return model_cls, appendix_cls


def _decode_float_tensor(tensor_proto: Any) -> np.ndarray:
    shape = tuple(int(d) for d in tensor_proto.dims)
    if tensor_proto.raw_data:
        arr = np.frombuffer(tensor_proto.raw_data, dtype="<f4").copy()
    else:
        arr = np.asarray(list(tensor_proto.float_data), dtype=np.float32)
    return arr.reshape(shape)


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    val = 0
    shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        val |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return val, pos
        shift += 7


def _encode_varint(val: int) -> bytes:
    out = bytearray()
    while val >= 0x80:
        out.append((val & 0x7F) | 0x80)
        val >>= 7
    out.append(val)
    return bytes(out)


def build_feature_extractor_bytes(base_bytes: bytes) -> tuple[bytes, dict[str, Any]]:
    """Verify upstream MobileNetV2-12 graph structure and append penultimate embedding output."""
    base_sha = _sha256_hex(base_bytes)
    if base_sha != EXPECTED_BASE_SHA256:
        raise RuntimeError(
            f"Upstream mobilenetv2-12.onnx SHA-256 mismatch: expected {EXPECTED_BASE_SHA256}, got {base_sha}"
        )

    model_cls, appendix_cls = _build_onnx_proto_classes()
    parsed = model_cls()
    parsed.ParseFromString(base_bytes)

    inits = {t.name: t for t in parsed.graph.initializer}
    nodes_by_out = {out_name: n for n in parsed.graph.node for out_name in n.output}

    if "output" not in nodes_by_out:
        raise RuntimeError("Final 'output' node not found in MobileNetV2-12 ONNX graph.")
    final_gemm = nodes_by_out["output"]
    if final_gemm.op_type != "Gemm" or len(final_gemm.input) < 3:
        raise RuntimeError(f"Unexpected classifier head op_type={final_gemm.op_type!r}.")

    feat_tensor_name = final_gemm.input[0]
    weight_name = final_gemm.input[1]
    bias_name = final_gemm.input[2]
    if feat_tensor_name != PENULTIMATE_TENSOR_NAME:
        raise RuntimeError(
            f"Expected penultimate tensor {PENULTIMATE_TENSOR_NAME!r}, found {feat_tensor_name!r}."
        )
    if weight_name not in inits or bias_name not in inits:
        raise RuntimeError("Classifier weight/bias initializers missing from ONNX graph.")

    cls_weight = _decode_float_tensor(inits[weight_name])
    cls_bias = _decode_float_tensor(inits[bias_name])
    if cls_weight.shape != (1000, EXPECTED_EMBEDDING_DIM):
        raise RuntimeError(
            f"Unexpected classifier weight shape {cls_weight.shape}; expected (1000, {EXPECTED_EMBEDDING_DIM})."
        )

    reshape_node = nodes_by_out.get(feat_tensor_name)
    if reshape_node is None or reshape_node.op_type != "Reshape":
        raise RuntimeError("Penultimate tensor is not produced by expected Reshape node.")
    gap_node = nodes_by_out.get(reshape_node.input[0])
    if gap_node is None or gap_node.op_type != "GlobalAveragePool":
        raise RuntimeError("Reshape input is not produced by GlobalAveragePool.")

    appendix = appendix_cls()
    id_node = appendix.node.add(op_type="Identity", name="Identity_embedding_1280")
    id_node.input.append(PENULTIMATE_TENSOR_NAME)
    id_node.output.append(EXPOSED_EMBEDDING_NAME)

    emb_out = appendix.output.add(name=EXPOSED_EMBEDDING_NAME)
    emb_out.type.tensor_type.elem_type = 1  # TensorProto.FLOAT
    emb_out.type.tensor_type.shape.dim.add(dim_param="batch_size")
    emb_out.type.tensor_type.shape.dim.add(dim_value=EXPECTED_EMBEDDING_DIM)
    appendix_bytes = appendix.SerializeToString()

    pos = 0
    patched = bytearray()
    patched_graph = False
    while pos < len(base_bytes):
        tag_start = pos
        tag, pos = _read_varint(base_bytes, pos)
        field_num = tag >> 3
        wire_type = tag & 0x7
        if wire_type == 0:
            _, pos = _read_varint(base_bytes, pos)
            patched.extend(base_bytes[tag_start:pos])
        elif wire_type == 1:
            pos += 8
            patched.extend(base_bytes[tag_start:pos])
        elif wire_type == 5:
            pos += 4
            patched.extend(base_bytes[tag_start:pos])
        elif wire_type == 2:
            length, data_start = _read_varint(base_bytes, pos)
            pos = data_start + length
            if field_num == 7 and not patched_graph:
                patched_graph = True
                merged_graph = base_bytes[data_start:pos] + appendix_bytes
                patched.extend(_encode_varint(tag))
                patched.extend(_encode_varint(len(merged_graph)))
                patched.extend(merged_graph)
            else:
                patched.extend(base_bytes[tag_start:pos])
        else:
            raise RuntimeError(f"Unsupported protobuf wire_type={wire_type} in ONNX ModelProto.")

    if not patched_graph:
        raise RuntimeError("ModelProto.graph field (7) was not found.")

    variant_bytes = bytes(patched)

    # Immediate numerical & structural verification in ONNX Runtime CPUExecutionProvider
    s_orig = ort.InferenceSession(base_bytes, providers=["CPUExecutionProvider"])
    s_var = ort.InferenceSession(variant_bytes, providers=["CPUExecutionProvider"])
    outputs_meta = [(o.name, list(o.shape), o.type) for o in s_var.get_outputs()]
    if len(outputs_meta) != 2 or outputs_meta[1][0] != EXPOSED_EMBEDDING_NAME:
        raise RuntimeError(f"Unexpected variant output signature: {outputs_meta}")
    if outputs_meta[1][1][1] != EXPECTED_EMBEDDING_DIM:
        raise RuntimeError(f"Unexpected embedding dimension in ONNX output: {outputs_meta[1]}")

    rng = np.random.default_rng(20260403)
    probe = rng.standard_normal((2, 3, 224, 224), dtype=np.float32)
    orig_logits = s_orig.run(None, {"input": probe})[0]
    var_logits, var_emb = s_var.run(None, {"input": probe})

    max_logit_diff = float(np.max(np.abs(orig_logits - var_logits)))
    if max_logit_diff > 0.0:
        raise RuntimeError(f"Logits diverged from upstream MobileNetV2-12: max_diff={max_logit_diff}")

    reconstructed_logits = var_emb @ cls_weight.T + cls_bias[None, :]
    max_linear_diff = float(np.max(np.abs(reconstructed_logits - var_logits)))
    if max_linear_diff > 1e-4:
        raise RuntimeError(
            f"Extracted tensor does not match penultimate Gemm input: max_diff={max_linear_diff}"
        )

    audit = {
        "role": "stage2_crop_species_and_embedding_extractor",
        "filename": VARIANT_MODEL_PATH.name,
        "parent_filename": BASE_MODEL_PATH.name,
        "parent_sha256": base_sha,
        "architecture": (
            "MobileNetV2 (opset 12, 224x224) dual-output graph exposing 1000-class breed logits "
            "and verified 1280-D penultimate GlobalAveragePool features"
        ),
        "build_script": "scripts/build_mobilenetv2_feature_extractor.py",
        "license": "Apache-2.0",
        "size_bytes": len(variant_bytes),
        "sha256": _sha256_hex(variant_bytes),
        "input_name": "input",
        "input_shape": ["batch_size", 3, 224, 224],
        "source_intermediate_tensor": PENULTIMATE_TENSOR_NAME,
        "upstream_tail_chain": [
            f"{gap_node.name} ({gap_node.op_type})",
            f"{reshape_node.name} ({reshape_node.op_type}) -> {PENULTIMATE_TENSOR_NAME}",
            f"{final_gemm.name} ({final_gemm.op_type}, weight=[1000, 1280]) -> output",
        ],
        "added_node": "Identity_embedding_1280 (Identity: '472' -> 'embedding_1280')",
        "outputs": [
            {"name": "output", "shape": ["batch_size", 1000], "type": "tensor(float)"},
            {"name": EXPOSED_EMBEDDING_NAME, "shape": ["batch_size", EXPECTED_EMBEDDING_DIM], "type": "tensor(float)"},
        ],
        "embedding_dim": EXPECTED_EMBEDDING_DIM,
        "normalization": "L2 unit vector (float32 inference, compact float16 base64 storage)",
        "verification": {
            "max_abs_logit_diff_vs_original": max_logit_diff,
            "max_abs_gemm_reconstruction_error": round(max_linear_diff, 8),
        },
    }
    return variant_bytes, audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", type=Path, default=BASE_MODEL_PATH)
    parser.add_argument("--out-model", type=Path, default=VARIANT_MODEL_PATH)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args(argv)

    base_bytes = args.base_model.read_bytes()
    variant_bytes, audit = build_feature_extractor_bytes(base_bytes)
    args.out_model.write_bytes(variant_bytes)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest["pipeline_id"] = "petcare-ai4-0c-local-vision-and-embeddings-v1"
    manifest["derived_variants"] = [audit]
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Built {args.out_model.name} ({audit['size_bytes']} bytes, sha256={audit['sha256']}) "
        f"with verified {audit['embedding_dim']}-D penultimate output '{EXPOSED_EMBEDDING_NAME}'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

