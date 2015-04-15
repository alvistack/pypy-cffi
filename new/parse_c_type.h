#include <stdint.h>


typedef void *_cffi_opcode_t;

#define _CFFI_OP(opcode, arg)   (_cffi_opcode_t)(opcode | (((uintptr_t)(arg)) << 8))
#define _CFFI_GETOP(cffi_opcode)    ((unsigned char)(uintptr_t)cffi_opcode)
#define _CFFI_GETARG(cffi_opcode)   (((uintptr_t)cffi_opcode) >> 8)

#define _CFFI_OP_PRIMITIVE       1
#define _CFFI_OP_POINTER         3
#define _CFFI_OP_ARRAY           5
#define _CFFI_OP_OPEN_ARRAY      7
#define _CFFI_OP_STRUCT_UNION    9
#define _CFFI_OP_ENUM           11
#define _CFFI_OP_TYPENAME       13
#define _CFFI_OP_FUNCTION       15
#define _CFFI_OP_FUNCTION_END   17
#define _CFFI_OP_NOOP           19
#define _CFFI_OP_BITFIELD       21
#define _CFFI_OP_CPYTHON_BLTN_V 23   // varargs
#define _CFFI_OP_CPYTHON_BLTN_N 25   // noargs
#define _CFFI_OP_CPYTHON_BLTN_O 27   // O  (i.e. a single arg)

#define _CFFI_PRIM_VOID          0
#define _CFFI_PRIM_BOOL          1
#define _CFFI_PRIM_CHAR          2
#define _CFFI_PRIM_SCHAR         3
#define _CFFI_PRIM_UCHAR         4
#define _CFFI_PRIM_SHORT         5
#define _CFFI_PRIM_USHORT        6
#define _CFFI_PRIM_INT           7
#define _CFFI_PRIM_UINT          8
#define _CFFI_PRIM_LONG          9
#define _CFFI_PRIM_ULONG        10
#define _CFFI_PRIM_LONGLONG     11
#define _CFFI_PRIM_ULONGLONG    12
#define _CFFI_PRIM_FLOAT        13
#define _CFFI_PRIM_DOUBLE       14
#define _CFFI_PRIM_LONGDOUBLE   15
#define _CFFI__NUM_PRIM         16


struct _cffi_global_s {
    const char *name;
    void *address;
    _cffi_opcode_t type_op;
};

struct _cffi_constant_s {
    const char *name;
    unsigned long long value;
    _cffi_opcode_t type_op;
};

struct _cffi_struct_union_s {
    const char *name;
    size_t size;
    int alignment;
    int flags;               // CT_UNION?  CT_IS_OPAQUE?
    int num_fields;
    int first_field_index;   // -> _cffi_fields array
};
#define CT_UNION            128
#define CT_IS_OPAQUE        4096

struct _cffi_field_s {
    const char *name;
    size_t field_offset;
    size_t field_size;
    _cffi_opcode_t field_type_op;
};

struct _cffi_enum_s {
    const char *name;
    _cffi_opcode_t integer_type_op;
};

struct _cffi_typename_s {
    const char *name;
    _cffi_opcode_t type_op;   /* 0 if opaque or prebuilt */
};

struct _cffi_type_context_s {
    _cffi_opcode_t *types;
    const struct _cffi_global_s *globals;
    const struct _cffi_constant_s *constants;
    const struct _cffi_struct_union_s *structs_unions;
    const struct _cffi_field_s *fields;
    const struct _cffi_enum_s *enums;
    const struct _cffi_typename_s *typenames;
    int num_globals;
    int num_constants;
    int num_structs_unions;
    int num_enums;
    int num_typenames;
};

struct _cffi_parse_info_s {
    const struct _cffi_type_context_s *ctx;
    _cffi_opcode_t *output;
    int output_size;
    size_t error_location;
    const char *error_message;
};

int parse_c_type(struct _cffi_parse_info_s *info, const char *input);
int search_in_globals(const struct _cffi_type_context_s *ctx,
                      const char *search, size_t search_len);